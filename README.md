# AIHOT_Fine

面向中文财经资讯的采集与 AI 编辑流水线：把多家财经信源统一成 RSS，再经过预筛、评分、聚类成事件、热度排序，产出日报 / 周报 / 月报。

本仓库是 AIHOT 框架的**财经行业定制版**，包含站点包（`site-src/`）、行业包（`industry-src/`）与财经信源桥接服务。

## 目录结构

| 路径 | 说明 |
|---|---|
| `finance-rss-server.py` | 财经信源 RSS 桥接服务。覆盖财联社、东方财富、同花顺、金十、华尔街见闻、证监会、央行、发改委、新浪财经、上海证券报等源，输出标准 RSS 2.0 |
| `patch_bridge.py` | 对桥接服务打补丁的辅助脚本（新增政务与财经站点处理器、GBK 解码、浏览器伪装请求头） |
| `cnstock.html` | 上海证券报页面的抓取样本，用作解析规则的回归基准 |
| `scope.ts` | 条目可见性判定模块，负责精选池、日报 / 周报 / 月报的发布条件 |
| `site-src/` | 站点包：站名文案、品牌资源、页面、模型配置、模块清单 |
| `industry-src/` | 行业包：分类词表、主题目录、信源、精选门槛、全部提示词 |

## 快速开始

### 1. 配置模型密钥

所有模型密钥一律通过环境变量注入，仓库内不存放任何凭据：

```bash
LLM_BASE_URL=https://your-endpoint/v1
LLM_MODEL=your-model
LLM_API_KEY=sk-xxxxxxxx

# 可选：具名模型（站点包 models.ts 中引用）
ZHIPU_BASE_URL=
ZHIPU_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
XIAOMI_MIMO_BASE_URL=
XIAOMI_MIMO_API_KEY=
```

### 2. 启动信源桥接服务

```bash
PORT=8053 \
PUBLIC_BASE_URL=https://your-domain \
python finance-rss-server.py
```

可用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `8053` | HTTP 监听端口 |
| `CDP_URL` | `http://localhost:9222` | Chrome 远程调试地址，用于需要执行 JS 的源 |
| `CACHE_TTL` | `300` | 缓存有效期（秒） |
| `REQUEST_TIMEOUT` | `10` | 单次请求超时（秒） |
| `PUBLIC_BASE_URL` | — | 生成绝对链接时使用的对外地址 |

雪球等需要 CDP 模式的源还需安装可选依赖：

```bash
pip install websocket-client
```

### 3. 安装站点包与行业包

两个包都是 TypeScript 源包，通过 `exports` 字段直接映射到 `.ts` 文件：

```bash
npm install ./site-src ./industry-src
```

## 配置要点

### 站点包（`site-src/`）

- `site.ts` —— 站名、行业词、出刊时间、首页与关于页文案、报头字、分类列表、备案号
- `models.ts` —— 每一步骤用哪个模型，未显式指定的步骤回落到 `LLM_*` 环境变量
- `brand/` —— 图标、Logo、分享图字标、日报 / 周报 / 月报报头
- `pages/` —— 使用规则、隐私说明模板（上线前按实际情况改写）
- `modules/` —— 启用哪些模块，模块实现放在仓库根目录 `modules/<名字>/`

### 行业包（`industry-src/`）

- `taxonomy.ts` —— 分类、标签、公司与机构词表
- `topics.json` —— 主题目录，站点启动时读取
- `sources.json` —— 首次启动导入的示范信源
- `selection.ts` —— 入选门槛
- `prompts/` —— 预筛、评分、写作、归组、事件综述、周期报告、翻译各步骤的提示词

## 数据流

```
信源 → RSS 桥接服务 → 预筛 → 独立两次打分 → 向量聚类成事件
                                            ↓
                          热度排序（48h 独立来源去重 / 24h 减半）
                                            ↓
                          日报 / 周报 / 月报
```

## 说明

本仓库基于开源框架 AIHOT 定制，`site-src/` 与 `industry-src/` 在使用时请遵循上游项目对品牌名称与 Logo 的使用约定，不要直接以框架名义对外发布。

站点包与行业包中的 `pages/privacy.md`、`pages/terms.md` 为模板，上线前需按实际运营主体改写。

## 许可

本仓库为内部定制版本，仅授权仓库所有者及其授权人员使用。
