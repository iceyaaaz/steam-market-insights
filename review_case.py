"""Build review evidence and counts from a fixed, assistant-coded sample.

No model API, sentiment classifier or keyword scoring is used at runtime.
Annotations are qualitative judgments and require human review before stronger claims.
"""
from pathlib import Path
import argparse
import json
import hashlib
import pandas as pd
from analytics import ROOT, safe_csv
from report import table

THEMES = {'p':'谜题与引导','s':'剧情与角色','v':'内容量与价格感受',
          'u':'操作与技术','a':'美术音乐与配音','l':'本地化','o':'笼统评价／信息不足'}
# + = explicit praise, - = explicit complaint, 0 = neutral/insufficient.
# More than one polarity per theme is allowed when the review is mixed.
ANNOTATIONS = {
'DP01':('o0','仅笼统表示可爱，没有足够内容判断具体原因。'),
'DP02':('p+','认为作品易于上手，谜题逻辑较前作清楚。'),
'DP03':('p+ s+ v+','喜欢角色互动和幽默对话，认为谜题难度适中，虽短仍感到满意。'),
'DP04':('p+ v-','喜欢较容易的谜题，但明确觉得流程太短。'),
'DP05':('s+ a+ p-','喜欢幽默与配音，部分推理即使有提示仍难理解。'),
'DP06':('p+ s+','认可提示系统和角色群像。'),
'DP07':('v0 o0','认为短小、简单有趣；没有明确说明短流程导致不满。'),
'DP08':('s+','喜欢侦探题材的戏仿与趣味。'),
'DP09':('a+ v0','称赞配音和美术，提及流程很短但未明确表达因此不满。'),
'DP10':('o0','仅对角色表达一句情绪，无法可靠归类具体体验。'),
'DN01':('p- s- v- u- a-','不喜欢填空推理及人物台词，抱怨移动与加载、体量和价格，认为宣传场景与体验预期有差距。'),
'DN02':('v- s+','认可质量与剧情，但认为流程过短、不值购买价格。'),
'DN03':('p- v- s0','认为难度偏低、体量与价格不匹配；对剧情同时提及简单和比前作有趣，按中性记录。'),
'DN04':('p- v-','不喜欢填空式玩法，并批评流程短。'),
'DN05':('a+ s- v0','认可美术与配音，但不喜欢写作和故事；提及短流程，并非明确价格投诉。'),
'DN06':('s- p- a+','认为剧情和关键词推理不够顺畅，认可美术及配音。'),
'DN07':('s- a+ p+','认可视觉与基本推理，主要不喜欢主角性格及幽默表达。'),
'DN08':('p- s- v-','批评谜题、剧情、体量及价格。'),
'DN09':('p+ s- v-','认可提示改善，但认为叙事目标不清、解谜回报感不足且流程太短。'),
'DN10':('v-','明确抱怨流程极短。'),
'SP01':('s+ a+ p+ p- u- l- v-','喜欢人物、美术和谜题多样性，也抱怨卡关、错误、英文表达及结尾不完整；涉及历史章节售卖的陈述未作事实认定。'),
'SP02':('a+ s+','认可治愈画风与作品立意。'),
'SP03':('v-','询问为何无法游玩第三章；具体原因不明，不据此判定当前章节缺失。'),
'SP04':('p- s-','虽然推荐，仍认为部分解谜与画风不协调，更期待轻松而非阴谋剧情。'),
'SP05':('s+ a+ p+ p- v-','喜欢故事、音乐和美术，认为部分谜题不够理想、新章节更清楚，同时称故事尚未结束。'),
'SP06':('a+ s+ p+ v+ u- l0','喜欢美术、故事与轻松解谜，认为章节已有足够内容；提及小错误，英文表达虽有奇怪之处但可接受。'),
'SP07':('a+','认可海边小镇画风与放松感；摘要省略与研究无关的个人经历。'),
'SP08':('a+','认可美术和温馨氛围。'),
'SP09':('a+ s+ l- u-','喜欢美术和故事，但认为英文翻译及自动滚动文字打断体验。'),
'SP10':('a+ p- s+ s-','喜欢美术及后续章节叙事；认为初期冗杂且引导不足，有时需要攻略。'),
'SN01':('a+ s+ p-','认可美术、音乐与剧情，但认为解谜提示不足，需查攻略才能继续。'),
'SN02':('a+ s- p-','认可美术，但批评剧情与谜题逻辑，认为必须搜索解法。'),
'SN03':('a+ o0','仅明确认可美术，对其余部分的批评过于笼统，未强行分类。'),
'SN04':('l-','询问法语版本何时提供，反映语言需求。'),
'SN05':('a+ s+ p- v-','认可美术和章节故事，抱怨引导不足与内容完整性、付费预期；未复述未经核实的制作组传闻。'),
'SN06':('p- u- s- v- a+','认可美术音乐，抱怨交互提示、对话状态、移动速度、部分剧情逻辑与内容完整性。'),
'SN07':('v- a+','认可画风，但认为内容突然结束、体量与价格不相称。'),
'SN08':('a+ u- s- v-','称赞美术与音乐，抱怨移动慢、节奏拖沓及内容完整性；后续收费说法作为当时感受保留而非当前事实。'),
'SN09':('a+ p- s0','认可画风，认为对不常玩解谜的人引导不足；剧情评价较中性。'),
'SN10':('a+ u-','认可美术，但认为重复跑图做任务麻烦。'),
}


def build(source=None):
    out=ROOT/'reports/cozy/reviews'
    sample_file = source/'sample.json' if source else out/'evidence.json'
    manifest_file = source/'manifest.json' if source else out/'sampling_manifest.json'
    samples = json.loads(sample_file.read_text(encoding='utf-8'))
    signature='\n'.join(sorted(r['sample_id']+':'+r['review_id']+':'+r['updated_utc'] for r in samples))
    if hashlib.sha256(signature.encode()).hexdigest() != '7aa208c428e6a88676705ae16d0d1f166e4b65623161a165e5b99efcf9485048':
        raise ValueError('Review sample changed. Re-read and recode it; never apply old annotations to a new sample.')
    assert {r['sample_id'] for r in samples} == set(ANNOTATIONS)
    out.mkdir(parents=True,exist_ok=True)
    evidence, codes = [], []
    for row in samples:
        labels, summary = ANNOTATIONS[row['sample_id']]
        clean = {k:v for k,v in row.items() if k!='text'}
        clean.update(summary_zh=summary, codes=labels,
                     coding_method='assistant qualitative reading; no independent human second coder')
        evidence.append(clean)
        for label in labels.split():
            codes.append(dict(sample_id=row['sample_id'],game=row['game'],group=row['group'],
                              theme=THEMES[label[0]],polarity={'+':'赞扬','-':'抱怨','0':'中性或不足'}[label[1]]))
    ev=pd.DataFrame(evidence)
    coded=pd.DataFrame(codes).drop_duplicates()
    assert ev.review_id.is_unique
    assert ev.groupby(['game','group']).size().eq(10).all()
    count=(coded.groupby(['game','group','theme','polarity']).sample_id.nunique().rename('mentions').reset_index())
    count['stratum_size']=10
    assert count.mentions.le(count.stratum_size).all()
    (out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    for name, frame in [('evidence',ev),('theme_codes',coded),('theme_counts',count)]:
        (out/f'{name}.csv').write_bytes(safe_csv(frame))
    manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
    (out/'sampling_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    dates=ev.assign(date=ev.created_utc.str.slice(0,10)).groupby(['game','group']).agg(
        count=('sample_id','size'),first=('date','min'),last=('date','max')).reset_index()
    def number(game,group,theme,polarity):
        rows=count.loc[count.game.str.startswith(game)&count.group.eq(group)&count.theme.eq(theme)&count.polarity.eq(polarity)]
        return int(rows.mentions.sum())
    def link(sid):
        return f'[{sid}]({ev.set_index("sample_id").loc[sid,"url"]})'
    rows=[]
    for game in ev.game.unique():
        for group in ['positive','negative']:
            for theme in ['谜题与引导','剧情与角色','内容量与价格感受','操作与技术','美术音乐与配音','本地化']:
                rows.append({'游戏':'Duck Detective' if game.startswith('Duck') else 'Sunset Hills',
                    '抽样组':'好评10条' if group=='positive' else '差评10条','主题':theme,
                    '赞扬条数':number(game,group,theme,'赞扬'),'抱怨条数':number(game,group,theme,'抱怨')})
    compact=pd.DataFrame(rows)
    (out/'theme_summary.csv').write_bytes(safe_csv(compact))
    evidence_md=['# 40条评论的逐条摘要与标注','',
        '摘要均为中文转述，不是原文引用。主题标注由助手逐条阅读完成，尚未经独立人工复核。原文仅保存在本地工作目录，不包含在发布包。','',
        '| ID与原文链接 | 游戏／推荐状态 | 日期 UTC／语言 | 中文转述 | 主题标注 |',
        '| --- | --- | --- | --- | --- |']
    for row in evidence:
        readable='；'.join(THEMES[x[0]]+{'+' : '：赞扬','-':'：抱怨','0':'：中性或不足'}[x[1]] for x in row['codes'].split())
        evidence_md.append(f'| [{row["sample_id"]}]({row["url"]}) | {"Duck" if row["app_id"]==2714620 else "Sunset"}／{"推荐" if row["group"]=="positive" else "不推荐"} | {row["created_utc"][:10]}／{row["language"]} | {row["summary_zh"]} | {readable} |')
    (out/'evidence.md').write_text('\n'.join(evidence_md),encoding='utf-8')
    text=f'''# 玩家评论研究：把评分差异变成可验证的问题

## 我们做了什么

2026-10-09读取 Steam 公开评论接口，对 Duck Detective: The Ghost of Glamping 与 Sunset Hills 各取最近10条好评、10条差评，共40条。采用全部语言、全部购买来源，启用Steam默认的偏离主题过滤。按API返回顺序取前10条，没有挑选“更符合预期”的评论；四组均实际返回10条。

参数及响应哈希见 sampling_manifest.json；[逐条证据](evidence.md)包含40条中文转述与原文链接。API来源见 [Steamworks评论接口文档](https://partner.steamgames.com/doc/store/getreviews)。源正文留在本地工作目录，发布包仅保留分析转述与溯源元数据。

## 先看样本的限制

{table(dates.rename(columns={'game':'游戏','group':'组别','count':'条数','first':'最早日期UTC','last':'最晚日期UTC'}))}

“最近10条”不是同一个时间窗口。两款游戏的差评稀疏程度不同，不能直接比较主题出现次数来推断哪款游戏的问题更普遍。这40条也不是随机抽样；刻意各取一半好评和差评，不能算出总体好评率。

样本语言包括简体中文18条、英文16条，以及葡萄牙语、日语、繁体中文、韩语、波兰语、法语各1条。多语言理解和转述存在误差。6条非Steam直接购买，0条标为免费获得，0条标为抢先体验评价；不据此推断实际支付价格或游玩版本。

## 三个值得用于下一步测试的观察

### 1. 对短流程的评价不是一致的，关键是体验与预期是否相称

Duck Detective的10条差评中，**{number('Duck','negative','内容量与价格感受','抱怨')}条**明确抱怨体量、流程长度或价格感受，例如{link('DN02')}、{link('DN03')}、{link('DN10')}。但好评{link('DP03')}认为短时间内也获得了满意体验，{link('DP04')}推荐游戏同时认为流程过短。仅说“短”但没有明确抱怨的DP07、DP09按中性记载，没有算成负面。

**可执行建议：**在原型试玩和商店描述评审中，同时检查“预计体验时长是否清楚”和“玩家是否觉得过程充实”。不要机械延长流程，也不要仅根据这些评论降价。记录玩家预期时长、实际试玩时长与价值感受，结合预算再讨论发行价。

### 2. 美术获得认可，不代表解谜引导也没有问题

Sunset Hills的10条差评中，**{number('Sunset','negative','美术音乐与配音','赞扬')}条**仍明确认可美术或音乐；其中**{number('Sunset','negative','谜题与引导','抱怨')}条**提到谜题逻辑或引导方面的问题，例如{link('SN01')}、{link('SN02')}、{link('SN06')}、{link('SN09')}。好评{link('SP10')}也提及早期引导不足。这说明“推荐／不推荐”与“每个具体方面的好坏”需要分开标注。

**可执行建议：**制作一段完整小关卡，观察首次接触的玩家能否识别可交互物品、理解下一目标及使用提示。记录首次求助时间、卡关位置、无效交互次数和提示后能否继续。测试后再决定是否修改引导，不能仅靠美术投入解决所有体验问题。

### 3. 历史抱怨不能直接作为当前产品事实

Sunset Hills的一些评论批评内容未完或后续收费；但较新的好评{link('SP06')}对章节内容量持不同看法。此次核查的[官方商店页](https://store.steampowered.com/app/1791590/Sunset_Hills/?l=english)说明未来内容将免费更新，并列出免费章节。因此只能写“部分受访评论表达过这一担忧”，不能声称当前一定需要额外付费。

**可执行建议：**把内容范围、已包含章节与更新承诺写清楚；研究评论时按时间及可确认的版本分开。仅有评论发布时间还不足以确定玩家实际体验的版本。

## 标注方法与可复核性

每条评论可标多个主题：谜题与引导、剧情与角色、内容量与价格感受、操作与技术、美术音乐与配音、本地化。每个主题分别标赞扬、抱怨或中性／信息不足；同一评论同一主题允许同时赞扬与抱怨。笼统短评不强行推断具体原因。主题计数按唯一评论ID去重，不按一句话出现次数计数。

标注由AI助手逐条阅读完成，没有调用项目中的大模型API，没有经过第二位独立人工编码者复核，也未测量标注一致性。中文转述不是原文引用，涉及玩家个人健康经历及未经核实的传闻不用于业务分析。这是探索性的定性研究，不能证明造成评分差异的因果关系。

完整主题计数见 theme_summary.csv；元数据与摘要见 evidence.csv；逐条标注见 theme_codes.csv。采集时间独立于Kaggle快照日期，不能把新评论作为对旧快照评分的精确解释。

## 本轮结论

案例已从“价格与评分比较”推进到“可验证的体验问题”：优先研究谜题引导、价值预期和内容范围沟通。下一步如真实开发产品，需要试玩和更大样本验证；作为求职案例，本轮已完成从业务问题、筛选、核查到建议与局限的闭环。
'''
    (out/'review_report.md').write_text(text,encoding='utf-8')
    print(compact.to_string(index=False))
    print('Evidence coverage:',len(ev),'reviews; all annotations matched and counts reconciled.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path)
    build(p.parse_args().source)
