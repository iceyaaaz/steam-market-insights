from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from analytics import (ROOT, BANDS, load_data, filter_games, price_summary, tag_summary,
                       release_trend, kpis, narrative, sql_query, safe_csv)
from tag_labels import tag_label, tag_zh

st.set_page_config(page_title='Steam 市场洞察', page_icon='🎮', layout='wide')
st.markdown('''<style>
.block-container {padding-top:4rem; max-width:1500px;}
[data-testid="stMetric"] {background:#141E30;border:1px solid #25344D;border-radius:12px;padding:18px;}
h1 {letter-spacing:-1.3px;} h3 {letter-spacing:-.4px;}
</style>''', unsafe_allow_html=True)


@st.cache_data
def data():
    return load_data()


def chart(fig, percent_y=False):
    fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Arial, Microsoft YaHei', size=13),
                      margin=dict(l=10, r=10, t=30, b=15), height=390,
                      colorway=['#67E8C3', '#72A9FF', '#D3B2FF', '#FFC878'])
    if percent_y:
        fig.update_yaxes(tickformat='.0%')
    st.plotly_chart(fig, width='stretch')


def pct(value):
    return f'{value:.1%}' if pd.notna(value) else '暂无'


try:
    games, tags, metadata = data()
except FileNotFoundError:
    st.error('缺少处理后的数据。请先运行 python pipeline.py，再运行 python report.py。')
    st.stop()

min_year, max_year = int(games.release_year.min()), int(games.release_year.max())
with st.sidebar:
    st.markdown('### STEAM / MARKET LAB')
    st.caption('数据分析作品 · 无 AI 版本')
    st.divider()
    years = st.slider('发售年份', min_year, max_year, (min_year, max_year))
    bands = st.multiselect('快照价格带 · USD', BANDS, default=BANDS)
    chosen = st.multiselect('游戏标签（满足任意一个）', sorted(tags.tag.unique()), format_func=tag_label)
    minimum = st.select_slider('最低评价数', [0, 20, 100, 500, 1000, 10000], value=100)
    no_discount = st.checkbox('仅看明确无折扣的记录')
    query = st.text_input('搜索游戏名称', placeholder='例如：Stardew Valley')
    st.caption('所有图表、指标和明细均使用当前筛选。默认 ≥100 条评价，适合口碑比较；看发行结构时可调到 0。')
    st.divider()
    st.caption(f'Kaggle v{metadata["version"]} · 更新 {metadata["source_updated"]}')
    st.link_button('查看数据来源', metadata['source_url'])

selected = filter_games(games, tags, years, bands, chosen, minimum, no_discount, query)
st.caption('STEAM MARKET INTELLIGENCE  /  PORTFOLIO 01')
st.title('从游戏市场，读懂机会与口碑')
st.write('探索价格、标签与玩家评价之间的关系，为品类研究和竞品选择提供证据。')
st.caption(f'数据版本更新于 {metadata["source_updated"]}，并非实时数据。价格为美元快照价格；评价量不等于销量。')

if selected.empty:
    st.warning('当前条件下没有游戏。请清除名称或标签筛选，或降低最低评价数。')
    st.stop()

metrics = kpis(selected)
cols = st.columns(4)
cols[0].metric('筛选游戏数', f'{metrics["games"]:,}')
cols[1].metric('快照价格中位数', f'${metrics["median_price"]:.2f}' if pd.notna(metrics['median_price']) else '暂无')
cols[2].metric('游戏好评率中位数', pct(metrics['median_rate']))
cols[3].metric('评价加权好评率', pct(metrics['weighted_rate']))
st.caption('中位数：每款游戏权重相同；加权好评率：总好评数 ÷ 总评价数，更受热门游戏影响。零评价游戏不参与好评率计算。')

overview, price_tab, tag_tab, trend_tab, detail_tab, method_tab = st.tabs(
    ['市场概览', '价格与口碑', '标签竞争', '发行趋势', '游戏明细', '数据与方法'])
prices = price_summary(selected, tags)

with overview:
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader('游戏集中在哪些价位？')
        chart(px.bar(prices, x='price_band', y='games', text_auto=',',
                     labels={'price_band':'价格带 · USD', 'games':'游戏数'}, color_discrete_sequence=['#67E8C3']))
    with right:
        st.subheader('当前样本速读')
        for fact in narrative(selected, tags):
            st.write('• ' + fact)
        st.caption('由已计算指标生成的固定规则摘要，未调用大模型。相关性不能证明因果关系。')
    st.info('研究建议：先看全部样本的结构，再用评价门槛和标签筛选定位可比较的竞品；不要将少量高好评游戏直接认定为市场机会。')

with price_tab:
    st.subheader('价格与口碑：比较分布，而不只看平均值')
    rated = selected.dropna(subset=['positive_rate'])
    if rated.empty:
        st.info('当前样本没有有效评价，无法比较好评率。')
    else:
        chart(px.box(rated, x='price_band', y='positive_rate', points=False,
                     category_orders={'price_band':BANDS}, color_discrete_sequence=['#67E8C3'],
                     labels={'price_band':'价格带 · USD', 'positive_rate':'游戏好评率'}), True)
    st.dataframe(prices.rename(columns={'price_band':'价格带 USD','games':'游戏数',
        'rated_games':'有评价游戏数','median_positive_rate':'好评率中位数','weighted_positive_rate':'加权好评率',
        'median_reviews':'评价数中位数','high_rating_share':'好评率≥90%占比'}).style.format(
        {'好评率中位数':'{:.1%}', '加权好评率':'{:.1%}', '好评率≥90%占比':'{:.1%}', '评价数中位数':'{:,.0f}'}, na_rep='—'),
        hide_index=True, width='stretch')
    st.caption('箱线图展示中位数及四分位分布，不展示离群点。零价可能包含免费、限免或缺失价格被源站记为零的记录；不能据此断言全部是免费游戏。')

with tag_tab:
    st.subheader('标签竞争：规模、评价量与口碑一起看')
    st.caption('这里的标签描述玩法、题材或风格，不是游戏名称。中文为阅读释义；筛选项、图表悬停和下表保留英文原名，方便对照。')
    group_min = st.select_slider('每个标签最少游戏数', [10, 30, 100, 300], value=30)
    grouped = tag_summary(selected, tags, group_min)
    if grouped.empty:
        st.info('没有达到样本量门槛的标签，请降低标签游戏数门槛或放宽筛选。')
    else:
        grouped = grouped.assign(tag_display=grouped.tag.map(tag_label), tag_chinese=grouped.tag.map(tag_zh))
        left, right = st.columns(2)
        with left:
            top_tags = grouped.head(15).sort_values('median_positive_rate')
            chart(px.bar(top_tags,
                         x='median_positive_rate', y='tag', orientation='h',
                         hover_name='tag_display',
                         labels={'median_positive_rate':'好评率中位数','tag':'标签'},
                         color_discrete_sequence=['#67E8C3']).update_xaxes(tickformat='.0%')
                         .update_yaxes(tickmode='array', tickvals=top_tags.tag.tolist(),
                                       ticktext=top_tags.tag_chinese.tolist(), automargin=True))
        with right:
            chart(px.scatter(grouped, x='games', y='median_positive_rate', size='median_reviews',
                             size_max=42, hover_name='tag_display', log_x=True,
                             labels={'games':'标签游戏数（对数轴）', 'median_positive_rate':'好评率中位数',
                                     'median_reviews':'评价数中位数'}), True)
        st.caption('气泡大小代表评价数中位数；标签游戏数只是供给规模，不能单独证明竞争程度或需求。一个游戏可属于多个标签，标签数量不可相加作为市场总量。')
        tag_table = grouped.drop(columns=['tag_display'])
        tag_table = tag_table[['tag_chinese', 'tag'] + [c for c in tag_table.columns if c not in ['tag_chinese', 'tag']]]
        st.dataframe(tag_table.rename(columns={'tag_chinese':'中文解释','tag':'英文标签','games':'游戏数','median_positive_rate':'好评率中位数',
            'weighted_positive_rate':'加权好评率','median_reviews':'评价数中位数','median_price':'价格中位数 USD',
            'rating_rank':'口碑排名'}).style.format({'好评率中位数':'{:.1%}','加权好评率':'{:.1%}',
            '价格中位数 USD':'{:.2f}','评价数中位数':'{:,.0f}'}, na_rep='—'), hide_index=True, width='stretch')

with trend_tab:
    st.subheader('样本中的发行数量如何变化？')
    trend = release_trend(selected, tags, years, int(metadata['source_updated'][:4]))
    chart(px.bar(trend, x='release_year', y='games', color='partial_year',
                 color_discrete_map={False:'#72A9FF', True:'#FFC878'},
                 labels={'release_year':'发售年份','games':'游戏数','partial_year':'未完整年度'}))
    st.dataframe(trend.rename(columns={'release_year':'年份','games':'游戏数',
        'previous_year_games':'上年游戏数','yoy':'同比','partial_year':'未完整年度'}).style.format(
        {'同比':'{:+.1%}'}, na_rep='—'), hide_index=True, width='stretch')
    st.warning('这是当前样本按发售年份的分布，不是当年的完整市场档案。2026 年不完整，不计算同比；评价数筛选会偏向积累时间更长的老游戏。')

with detail_tab:
    st.subheader('回到具体游戏，核查你的判断')
    sort_by = st.selectbox('排序依据', ['评价数', '口碑可信下界', '好评率', '价格'])
    sort_col = {'评价数':'reviews','口碑可信下界':'wilson_lower','好评率':'positive_rate','价格':'price'}[sort_by]
    display = selected.sort_values([sort_col, 'app_id'], ascending=[False, True]).copy()
    display['store_url'] = 'https://store.steampowered.com/app/' + display.app_id.astype(str)
    columns = ['app_id','name','release_date','price','reviews','positive_rate','wilson_lower','peak_ccu','store_url']
    st.caption('屏幕展示排序前 500 款；下载包含当前筛选的全部游戏。口碑可信下界为 Wilson 95% 下界。Peak CCU 为源数据字段，其观测窗口不明确，不用作实时在线人数。')
    st.dataframe(display[columns].head(500), hide_index=True, width='stretch', column_config={
        'app_id':'Steam ID','name':'游戏','release_date':'发售日期',
        'price':st.column_config.NumberColumn('价格 USD', format='$%.2f'),
        'reviews':st.column_config.NumberColumn('评价数', format='%d'),
        'positive_rate':st.column_config.NumberColumn('好评率（0–1）', format='%.3f'),
        'wilson_lower':st.column_config.NumberColumn('Wilson 下界', format='%.3f'),
        'peak_ccu':'源数据 Peak CCU','store_url':st.column_config.LinkColumn('Steam 商店', display_text='查看')})
    st.download_button('下载筛选结果 CSV', safe_csv(display[columns]), 'steam_filtered.csv', 'text/csv')
    with st.expander('SQL 窗口函数示例：各价格带口碑前十'):
        st.dataframe(sql_query('05_rankings.sql', selected, tags), hide_index=True, width='stretch')

with method_tab:
    st.subheader('可信分析，始于明确口径')
    st.write('数据链路：Kaggle 固定版本 JSON → SQL 清洗与审计 → 游戏／标签 Parquet → SQL 聚合 + Pandas 分组分析 → Streamlit。')
    st.write('v52 CSV 表头将 Discount 与 DLC count 合并，导致后续字段错位；本项目使用同包 games.json。名称含 Demo、Playtest、Dedicated Server、Soundtrack 的记录按规则排除；该启发式不能完全识别所有非正式游戏。')
    st.write('快照价格不是发行定价；不估算销量或收入。数据版本日期不是每条记录的采集日期。价格、评价缺失值不填零；零评价的好评率为空。无有效日期、未来发售和无名称记录被审计排除。')
    st.json(metadata['quality'])
    audit = json.loads((ROOT / 'data/audit.json').read_text(encoding='utf-8'))
    st.dataframe(pd.DataFrame(audit), hide_index=True)
    st.caption(f'源 ZIP SHA-256：{metadata["archive_sha256"]}')
    report = ROOT / 'reports/analysis.md'
    if report.exists():
        st.download_button('下载完整业务分析报告', report.read_bytes(), 'steam_analysis.md', 'text/markdown')
    with st.expander('查看价格分析 SQL'):
        st.code((ROOT / 'sql/02_price_bands.sql').read_text(encoding='utf-8'), language='sql')

