# 11. 延伸阅读

xAI 没有技术报告，延伸阅读的价值排序是：**一手公告与供应商案例 > 有编辑流程的深度报道 > 第三方估算 > 自媒体汇总**（后两类在正文中均已标注为"据报道/未证实"）。以下链接截至 2026-10 均可访问。

## 一手来源（官方/供应商）

- [NVIDIA Newsroom：NVIDIA Ethernet Networking Accelerates World's Largest AI Supercomputer, Built by xAI](https://nvidianews.nvidia.com/news/spectrum-x-ethernet-networking-xai-colossus)（2024-10-28）——Colossus 数字的最权威来源：100k H100、Spectrum-X/SN5600/BlueField-3、95% 吞吐零丢包、122 天/19 天、翻倍至 200k。
- [Supermicro 官方案例：xAI Colossus](https://www.supermicro.com/fr/featured/xai-colossus)——整柜形态（4U × 8 台、64 卡/柜、DLC 机柜内 CDU）与"世界最大液冷 AI 集群"口径。
- [AWS Machine Learning Blog：Grok 4.6 on Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/xais-grok-4-6-is-now-available-in-amazon-bedrock/)——xAI 企业渠道（Bedrock）的官方确认；4.3/4.7 上架 Bedrock 亦有 AWS 侧公告。
- [xAI 官方公告存档](https://x.ai/news)（含 Grok-3、Grok-4、收购 X、"至少 100 万 GPU" 扩展宣言等；页面有反爬，部分需通过搜索引擎缓存访问）。
- [Grok-1 开源物料](https://github.com/xai-org/grok-1)——314B MoE 权重与模型卡（Apache 2.0）。

## 深度报道（按主题）

### 集群建设与供电

- [Data Center Dynamics：xAI gets go-ahead for 41 natural gas turbines in Mississippi](https://www.datacenterdynamics.com/en/news/musks-xai-gets-go-ahead-for-41-natural-gas-turbines-in-mississippi-to-power-colossus-data-centers/)——南黑文（Southaven） 41 台永久轮机获批（2026-03）。
- [Data Center Dynamics：xAI deploys 19 natural gas turbines at Colossus 2](https://www.datacenterdynamics.com/en/news/xai-deploys-19-natural-gas-turbines-at-colossus-2-data-center-in-southaven-mississippi-report/)——Colossus 2 轮机部署的早期报道。
- [Reuters（经转引）：xAI ran 59 unpermitted gas turbines](https://aiweekly.co/alerts/xai-runs-59-unpermitted-gas-turbines-for-colossus-2-reuters-says)——59 台未许可轮机的调查口径。
- [World Energy / Gizmodo：SpaceX agrees to remove temporary gas turbines by 2027](https://www.world-energy.org/article/55673.html)——2027 拆机承诺。
- [Data Center Frontier：The Colossus Supercomputer](https://www.datacenterfrontier.com/machine-learning/article/55244139/the-colossus-ai-supercomputer-elon-musks-drive-toward-data-center-ai-technology-domination)——建设全程的跟踪报道汇总。

### 组织与人才

- [Fortune：Half of xAI's founding team has left](https://fortune.com/2026/02/11/half-of-xai-founding-team-has-left-elon-musks-ai-company-potentially-complicating-his-plans-for-a-blockbuster-spacex-ipo/)（2026-02-11）——创始团队过半离开的旗舰报道。
- [TechCrunch：Exactly half of xAI's founding team has left](https://techcrunch.com/2026/02/10/okay-now-exactly-half-of-xais-founding-team-has-left-the-company/)（2026-02-10）。
- [Fast Company：Inside the xAI exodus](https://www.fastcompany.com/91531084/inside-the-xai-exodus)——离职者去向的长报道。
- [Data Center Dynamics：Musk's xAI sees spate of senior departures](https://www.datacenterdynamics.com/en/news/musks-xai-sees-spate-of-senior-departures-including-co-founders/)——高管流失汇总。

### 特斯拉协同与治理

- [Reuters：Musk unveils joint Tesla-xAI project 'Macrohard'](https://www.reuters.com/business/autos-transportation/musk-unveils-joint-tesla-xai-project-macrohard-eyes-software-disruption-2026-03-11/)（2026-03-11）——Digital Optimus 的官方级报道。
- [Electrek：Musk confirms xAI-Tesla joint 'Digital Optimus' project](https://electrek.co/2026/03/11/musk-confirms-xai-tesla-joint-digital-optimus-project-shareholder-lawsuit/)——含股东诉讼背景。
- [Drive Tesla Canada：Tesla shareholders reject proposed investment in xAI](https://driveteslacanada.ca/news/tesla-shareholders-reject-proposed-investment-in-xai/)——2025-11 股东投票插曲。

### 模型与分发

- [The Rundown：Grok 4.1](https://www.therundown.ai/tools/grok-4-1)——2025-11-17 发布的二手汇总（正文已标注来源等级）。
- [Unite AI：AWS adds Grok 4.7 to Bedrock](https://www.unite.ai/aws-adds-xais-grok-4-7-to-amazon-bedrock-with-500k-context-window/)——4.7/500K 上下文的二手确认（AWS 侧公告为一手）。
- [Business Insider：Amazon plans to add Grok models](https://www.businessinsider.com/amazon-spacex-grok-models-ai-offering-bedrock-2026-5)——Bedrock 合作的商业动机。

## 第三方估算（方法学公开，输入为推测）

- [Epoch AI](https://epoch.ai/)——Grok-4 训练成本/能耗/碳排放估算（约 4.9 亿美元、3.1 亿 kWh、14 万吨 CO2）的方法学源头；正文引用时已标注"第三方估算"。

## 手册内交叉引用

### 其他案例研究（09-case-study）

- [OpenAI 案例研究](/09-case-study/openai/)——多园区 Stargate vs 单园区 Colossus 的路线对赌。
- [Anthropic 案例研究](/09-case-study/anthropic/)——安全优先 + 租用算力起步的另一极；据报道又是 Colossus 的潜在租户。
- [Meta 案例研究](/09-case-study/meta/)——开放权重 + OCP 硬件 + 多中型集群的对照组。
- [Google 案例研究](/09-case-study/google/)——NSDI'24 可靠性工程：xAI 黑盒最该补齐的一课。
- [DeepSeek 案例研究](/09-case-study/deepseek/)——算力效率光谱的另一极：少量卡 + 算法创新。
- [Cursor 案例研究](/09-case-study/cursor/)——算力占有量的另一个极端：不拥有模型，靠产品工程纵深取胜。

### 基础与专项主题

- [计算机网络](/01-foundation/computer-networks/)——Spectrum-X/RoCE、RDMA、无损以太网与 Falcon 论文背景。
- [存储系统](/01-foundation/storage-systems/)——EB 级训练存储、checkpoint 与 RTO 设计。
- [分布式系统基础](/01-foundation/distributed-systems/)——同步训练的可用率乘积与故障模型。
- [GPU 与 CUDA 编程](/01-foundation/gpu-cuda/)——H100/GB200 的 TDP、NVLink 域与液冷密度的硬件基础。
- [AI SRE](/07-ai-sre/)——万卡集群可靠性工程的体系化方法；对照 xAI 的可靠性黑盒。
- [安全](/08-security/)——Grok 内容治理争议与模型分发的合规面。

## 小结

研究 xAI 的方法论本身就是一课：**一手供应商案例定数字、有编辑流程的媒体定事实、第三方估算定量级、传闻只配出现在脚注里**——这个证据分级纪律，比 Colossus 的任何单个数字都更值得带走。
