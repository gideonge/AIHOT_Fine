// 这个行业的分类体系：类别、标签词表、公司与机构名录，以及防止张冠李戴的身份词典。
// 模型按这里的词表打标签，主题页（topics.json）按标签归类，筛选栏按类别分组。
// 换行业时：类别的 key 会出现在网址里（/all?category=…），上线后就不要再改；标签和名录可以随时增减。

/**
 * 网页上的类别（筛选栏、卡片角标、RSS 分类订阅）。key 是网址和接口里的身份，上线后不要改。
 * section 是日报里的分节标题（几个类别可以共用一节，按这里的顺序排）；guide 告诉结构抽取模型这一类收什么、
 * 和相邻类别的边界在哪（总的归类原则写在 prompts/structure.md 里）。
 * commentary 标出评论类（解读、观点）：日报写过的事又有评论类的后续报道，只占一行快讯（报道它的信源够多时除外）。
 * 没归上类的资料在日报里放进第一个 key 为 industry 的类别所在的节（没有就放最后一节）。
 * feedLabel 是分类 RSS 标题里的名字（不写就用 label）。公开接口、RSS 和 MCP 里要把一类并进另一类发布，写在站点设置里（site/site.ts 的 PUBLIC_CATEGORIES）。
 */
export const CATEGORIES = [
  { key: "policy", label: "政策监管", feedLabel: "政策监管", section: "政策与监管", guide: "证监会、央行、国务院、发改委、交易所等监管与政策制定部门发布的规则、办法、征求意见稿、处罚决定、窗口指导，以及重要会议的定调。注意区分：针对个别公司的监管行动（立案、处罚）也归这里；公司对政策的回应归公司财报。" },
  { key: "market", label: "A股市场", feedLabel: "A股市场", section: "A股市场", guide: "大盘与指数（上证、深成、创业板、科创50、北证50）的涨跌、成交额、板块轮动、资金流向（北向资金、两融、龙虎榜）、指数编制调整、涨跌停与异常波动、开盘收盘数据等市场运行信息。个股行情归公司财报。" },
  { key: "company", label: "公司财报", feedLabel: "公司财报", section: "公司与财报", guide: "上市公司与发债主体的业绩快报、定期报告、业绩预告、分红方案、并购重组、定增可转债、回购与增减持、IPO与再融资、退市风险、股权激励、重大合同与经营公告。券商研报对个股的评级调整归这里。" },
  { key: "macro", label: "宏观经济", feedLabel: "宏观经济", section: "宏观经济", guide: "国家统计局、央行、海关总署、财政部等发布的经济运行数据（GDP、CPI、PPI、PMI、社融、M1/M2、固定资产投资、社零、进出口、就业）与货币财政操作（LPR、MLF、降准降息、公开市场操作）、重要部委经济形势表态。" },
  { key: "industry", label: "行业", feedLabel: "行业动态", section: "行业动态", guide: "行业层面的政策、景气度、价格与产能变化（如光伏组件价格、碳酸锂价格、猪价、运价）、产业链动态、行业会议与协会数据。注意：单一公司的经营动态归公司财报，多个公司所在的行业变化才归这里。" },
  { key: "global", label: "海外全球", feedLabel: "海外市场", section: "海外与全球", guide: "美股、欧股、港股、日股等外围市场的重要变化，美联储等海外央行政策，美元与人民币汇率、大宗商品（原油、黄金、铜、铁矿）价格，以及影响A股的地缘政治与国际贸易事件。" },
  { key: "ai", label: "AI要闻", feedLabel: "AI要闻", section: "AI要闻", guide: "仅收录对A股与全球市场有实质影响的重大AI动态：头部AI公司的重大发布或融资、影响AI板块的国家级监管政策、可能改变产业链格局的技术突破。日常AI资讯、评测、教程和普通产品更新不要归这里。" },
] as const satisfies ReadonlyArray<{ key: string; label: string; feedLabel?: string; section: string; guide: string; commentary?: true }>;

/**
 * 这个行业最受关注的一类发布（AI 行业是新模型）：日报报头的“N 个新模型”、改分类后修订已出的报告都按它数。
 * category 是类别，tag 是标签，两者都对上才算；unit 接在数字后面。
 * 没有这样一类的行业设成 null，报头就不显示这个数。
 */
export const RELEASE: { category: string; tag: string; unit: string } | null = null;

/** 周报月报的总述可以直接写、不必在报道里找到出处的行业通用词（小写）。站名会自动算进去。 */
export const PLAIN_TERMS: readonly string[] = ["a股", "gdp", "cpi", "ppi", "pmi", "ipo", "etf", "lpr", "mlf", "北向资金", "美联储", "证监会", "央行"];

/**
 * 内容理解一步给每篇资料判的“内容类型”（写在 prompts/content-understanding.md 里，改了类型要同步改那份提示词）。
 * 评分提示词（prompts/selection-score.md）按类型给五个维度不同的权重。
 */
export const ITEM_TYPES = ["policy_doc", "market_data", "earnings", "company_event", "macro_data", "opinion_analysis", "research_report"] as const;

// ── 标签词表 ────────────────────────────────────────────────────────────────────────────

/** 每篇资料的第一个标签必须是这些“分类标签”之一。 */
export const CATEGORY_TAGS = [
  "政策/监管", "A股/大盘", "资金流向", "板块/行业", "公司业绩", "财报/公告", "并购/重组", "回购/增减持", "IPO/上市", "宏观数据", "货币政策", "大佬观点", "研报/解读", "海外市场", "汇率/大宗", "AI要闻", "其他",
] as const;

/** 可选的主题标签（板块与题材）。 */
export const TOPIC_TAGS = [
  "新能源", "半导体", "AI算力", "机器人", "电动车", "光伏", "风电", "储能", "医药", "白酒", "食品饮料", "消费", "银行", "券商", "保险", "地产", "军工", "稀土", "煤炭", "有色", "钢铁", "化工", "农业", "通信", "计算机", "电子", "汽车", "家电", "游戏", "传媒", "交运", "公用事业",
] as const;

/** 可选的实体标签（重要上市公司与机构）。 */
export const ENTITY_TAGS = ["贵州茅台", "宁德时代", "比亚迪", "中芯国际", "招商银行", "中国平安", "隆基绿能", "东方财富", "紫金矿业", "中信证券", "长江电力", "五粮液", "美的集团", "恒瑞医药", "寒武纪", "工业富联", "中际旭创", "阳光电源", "海天味业", "立讯精密", "证监会", "央行", "国家统计局", "上交所", "深交所"] as const;

/** 模型常写的近义词，统一成词表里的写法。 */
export const TAG_SYNONYMS: Readonly<Record<string, string>> = {
  "政策": "政策/监管", "监管": "政策/监管", "法规": "政策/监管", "处罚": "政策/监管", "新规": "政策/监管", "规则": "政策/监管",
  "大盘": "A股/大盘", "股市": "A股/大盘", "A股": "A股/大盘", "行情": "A股/大盘", "指数": "A股/大盘", "涨停": "A股/大盘", "跌停": "A股/大盘",
  "北向资金": "资金流向", "两融": "资金流向", "龙虎榜": "资金流向", "主力": "资金流向", "融资": "回购/增减持", "资金": "资金流向",
  "业绩": "公司业绩", "业绩预告": "公司业绩", "快报": "公司业绩", "财报": "财报/公告", "公告": "财报/公告", "定期报告": "财报/公告", "分红": "财报/公告", "派息": "财报/公告",
  "并购": "并购/重组", "重组": "并购/重组", "收购": "并购/重组", "借壳": "并购/重组", "定增": "财报/公告", "可转债": "财报/公告",
  "回购": "回购/增减持", "增持": "回购/增减持", "减持": "回购/增减持", "举牌": "回购/增减持",
  "IPO": "IPO/上市", "上市": "IPO/上市", "新股": "IPO/上市", "注册制": "IPO/上市", "退市": "财报/公告",
  "GDP": "宏观数据", "CPI": "宏观数据", "PPI": "宏观数据", "PMI": "宏观数据", "社融": "宏观数据", "出口": "宏观数据", "进出口": "宏观数据", "就业": "宏观数据",
  "降准": "货币政策", "降息": "货币政策", "LPR": "货币政策", "MLF": "货币政策", "公开市场": "货币政策", "央行": "货币政策",
  "观点": "大佬观点", "评论": "大佬观点", "专访": "大佬观点", "解读": "研报/解读", "分析": "研报/解读", "研报": "研报/解读", "策略": "研报/解读",
  "美股": "海外市场", "港股": "海外市场", "美联储": "海外市场", "隔夜": "海外市场", "外围": "海外市场",
  "汇率": "汇率/大宗", "人民币": "汇率/大宗", "原油": "汇率/大宗", "黄金": "汇率/大宗", "大宗商品": "汇率/大宗", "铜": "汇率/大宗", "铁矿": "汇率/大宗",
  "AI": "AI要闻", "人工智能": "AI要闻", "算力": "AI算力", "大模型": "AI要闻",
  "行业": "板块/行业", "板块": "板块/行业", "题材": "板块/行业", "概念": "板块/行业", "赛道": "板块/行业",
};

// ── 公司与主体 ──────────────────────────────────────────────────────────────────────────

/**
 * 公司主题：id → 显示名、卡片上显示的标签（null 表示只用 entity:<id> 归类）、别名。
 * aliases 给结构抽取模型看；otherNames 是公司自己的其他称呼（官方账号名、子品牌），
 * 把事实的主体对到发布方时也认它们。
 */
export const ENTITIES: Record<string, { name: string; displayTag: string | null; aliases: string[]; otherNames?: string[] }> = {
  "maotai": { name: "贵州茅台", displayTag: "贵州茅台", aliases: ["贵州茅台", "茅台"], otherNames: ["600519"] },
  "catl": { name: "宁德时代", displayTag: "宁德时代", aliases: ["宁德时代", "CATL"], otherNames: ["300750"] },
  "byd": { name: "比亚迪", displayTag: "比亚迪", aliases: ["比亚迪", "BYD"], otherNames: ["002594"] },
  "smic": { name: "中芯国际", displayTag: "中芯国际", aliases: ["中芯国际", "SMIC"], otherNames: ["688981"] },
  "cmb": { name: "招商银行", displayTag: "招商银行", aliases: ["招商银行", "招行"], otherNames: ["600036"] },
  "pingan": { name: "中国平安", displayTag: "中国平安", aliases: ["中国平安", "平安"], otherNames: ["601318"] },
  "longi": { name: "隆基绿能", displayTag: "隆基绿能", aliases: ["隆基绿能", "隆基"], otherNames: ["601012"] },
  "eastmoney": { name: "东方财富", displayTag: "东方财富", aliases: ["东方财富"], otherNames: ["300059"] },
  "zijin": { name: "紫金矿业", displayTag: "紫金矿业", aliases: ["紫金矿业", "紫金"], otherNames: ["601899"] },
  "citic": { name: "中信证券", displayTag: "中信证券", aliases: ["中信证券"], otherNames: ["600030"] },
  "cpg": { name: "长江电力", displayTag: "长江电力", aliases: ["长江电力", "长电"], otherNames: ["600900"] },
  "wuliangye": { name: "五粮液", displayTag: "五粮液", aliases: ["五粮液"], otherNames: ["000858"] },
  "midea": { name: "美的集团", displayTag: "美的集团", aliases: ["美的集团", "美的"], otherNames: ["000333"] },
  "hengrui": { name: "恒瑞医药", displayTag: "恒瑞医药", aliases: ["恒瑞医药", "恒瑞"], otherNames: ["600276"] },
  "cambricon": { name: "寒武纪", displayTag: "寒武纪", aliases: ["寒武纪", "Cambricon"], otherNames: ["688256"] },
  "fii": { name: "工业富联", displayTag: "工业富联", aliases: ["工业富联", "富士康工业互联网"], otherNames: ["601138"] },
  "zhongji": { name: "中际旭创", displayTag: "中际旭创", aliases: ["中际旭创"], otherNames: ["300308"] },
  "sungrow": { name: "阳光电源", displayTag: "阳光电源", aliases: ["阳光电源"], otherNames: ["300274"] },
  "haitian": { name: "海天味业", displayTag: "海天味业", aliases: ["海天味业", "海天"], otherNames: ["603288"] },
  "luxshare": { name: "立讯精密", displayTag: "立讯精密", aliases: ["立讯精密", "立讯"], otherNames: ["002475"] },
  "csrc": { name: "中国证监会", displayTag: "证监会", aliases: ["证监会", "中国证监会"], otherNames: ["CSRC"] },
  "pbc": { name: "中国人民银行", displayTag: "央行", aliases: ["央行", "中国人民银行"], otherNames: ["PBOC"] },
  "stats": { name: "国家统计局", displayTag: "国家统计局", aliases: ["国家统计局", "统计局"], otherNames: [] },
  "sse": { name: "上海证券交易所", displayTag: "上交所", aliases: ["上交所", "上海证券交易所"], otherNames: ["SSE"] },
  "szse": { name: "深圳证券交易所", displayTag: "深交所", aliases: ["深交所", "深圳证券交易所"], otherNames: ["SZSE"] },
};

/**
 * 身份词典：摘要和标题里出现的公司，必须在原文里也出现过，否则退回原标题、丢掉摘要（防止模型张冠李戴）。
 * 行业没有这个问题时可以留空数组。
 */
export const IDENTITY_LEXICON: ReadonlyArray<{ id: string; name: string; patterns: RegExp[] }> = [
  { id: "maotai", name: "贵州茅台", patterns: [/贵州茅台|\bmaotai\b|茅台集团/i] },
  { id: "catl", name: "宁德时代", patterns: [/宁德时代|\bcatl\b/i] },
  { id: "byd", name: "比亚迪", patterns: [/比亚迪|\bbyd\b/i] },
  { id: "smic", name: "中芯国际", patterns: [/中芯国际|\bsmic\b/i] },
  { id: "cmb", name: "招商银行", patterns: [/招商银行|招行/i] },
  { id: "pingan", name: "中国平安", patterns: [/中国平安|\bpingan\b/i] },
  { id: "longi", name: "隆基绿能", patterns: [/隆基绿能|隆基股份|隆基/i] },
  { id: "eastmoney", name: "东方财富", patterns: [/东方财富|\beastmoney\b/i] },
  { id: "zijin", name: "紫金矿业", patterns: [/紫金矿业/i] },
  { id: "citic", name: "中信证券", patterns: [/中信证券/i] },
  { id: "cpg", name: "长江电力", patterns: [/长江电力|长电/i] },
  { id: "wuliangye", name: "五粮液", patterns: [/五粮液/i] },
  { id: "midea", name: "美的集团", patterns: [/美的集团|美的/i] },
  { id: "hengrui", name: "恒瑞医药", patterns: [/恒瑞医药|恒瑞/i] },
  { id: "cambricon", name: "寒武纪", patterns: [/寒武纪|\bcambricon\b/i] },
  { id: "fii", name: "工业富联", patterns: [/工业富联/i] },
  { id: "zhongji", name: "中际旭创", patterns: [/中际旭创/i] },
  { id: "sungrow", name: "阳光电源", patterns: [/阳光电源/i] },
  { id: "haitian", name: "海天味业", patterns: [/海天味业|海天/i] },
  { id: "luxshare", name: "立讯精密", patterns: [/立讯精密|立讯/i] },
  { id: "csrc", name: "中国证监会", patterns: [/证监会|\bcsrc\b/i] },
  { id: "pbc", name: "中国人民银行", patterns: [/中国人民银行|央行|\bpboc\b/i] },
  { id: "stats", name: "国家统计局", patterns: [/国家统计局/i] },
  { id: "sse", name: "上海证券交易所", patterns: [/上交所|上海证券交易所/i] },
  { id: "szse", name: "深圳证券交易所", patterns: [/深交所|深圳证券交易所/i] },
];

/** 这些域名上的文章，发布方就是对应的公司（托管平台如 GitHub、arXiv 不算）。 */
export const PUBLISHER_DOMAINS: ReadonlyArray<{ entityId: string; domains: readonly string[] }> = [
  { entityId: "csrc", domains: ["csrc.gov.cn"] },
  { entityId: "pbc", domains: ["pbc.gov.cn"] },
  { entityId: "stats", domains: ["stats.gov.cn"] },
  { entityId: "sse", domains: ["sse.com.cn"] },
  { entityId: "szse", domains: ["szse.cn", "szse.com"] },
];

/** 原文里的这些写法也算提到了对应公司。 */
export const IDENTITY_CONTEXT_ALIASES: ReadonlyArray<{ entityId: string; pattern: RegExp }> = [];
