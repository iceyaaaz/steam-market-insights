# 部署为可分享的看板

本交付包含可部署代码与处理后数据。公网发布还需要你的 GitHub 仓库与 Streamlit 登录账户；本地地址只在当前电脑上有效。

1. 创建 GitHub 仓库，将 steam-market 文件夹的内容放在仓库根目录。提交 app.py、analytics.py、requirements.txt、.streamlit/、sql/、data/、reports/、docs/ 等文件。不要上传原始 ZIP、虚拟环境或密钥。
2. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)，连接 GitHub，创建 app，选择仓库、分支和入口 `app.py`。
3. 选择 Python 3.13（与本地验证环境相同）。本项目没有 API 密钥，Secrets 留空。
4. 部署后检查市场概览、单标签筛选、无结果提示和 CSV 下载，并记录最终公网 URL。
5. 将 URL 放入 README 和简历。以后更新源数据时在本地重跑 pipeline.py 与 report.py，提交处理后数据与元数据，不在每次页面访问时下载原始包。

部署依赖官方说明：[准备与部署](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)。若运行环境内存受限，可先缩减带入界面的辅助文本字段；不要悄悄抽样却仍声称是全量分析。

## 本地验收清单

- `python -m pytest -q` 通过。
- `python -m streamlit run app.py` 启动成功。
- 默认页面显示真实数据，指标与分析报告同口径对得上。
- 选择多个标签不会重复计数；无结果时有清晰提示。
- 设置最低评价数为 0，零评价游戏好评率仍为空。
- 2026 年标为未完整年度，年度同比不误算。
- 下载文件与筛选结果一致，未包含任何账户秘密。
