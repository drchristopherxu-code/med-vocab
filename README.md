# 医学专有名词背诵 Vocab Trainer

一个**纯前端单文件**医学英语背单词应用（HTML + CSS + 原生 JavaScript），UWorld 风格界面。
词库共 **38 个 / 4822 个医学专有名词**（中英双语释义），来自两份词表：

| 词库组 | 来源 | 规模 |
|---|---|---|
| 核心精选（19 库） | 《20_医学专有名词解释_双语术语表.docx》（双语教科书式讲义 · 术语表卷） | 419 核心术语 |
| 学科全集（19 库，id 带 `-full`） | 《医学专有名词解释_英中双语.docx》（Kimi_Agent_知识点合并版素材） | 4403 词条 · 覆盖 19 个学科 |

## 使用方法

**双击 `index.html`** 即可在 Chrome / Edge / Safari 中打开，无需安装任何环境、无需网络。

> 语音功能使用浏览器原生 Web Speech API（强制 `en-US` 美音）；本地文件协议（`file://`）下可直接使用。
> 若希望以 http 方式访问：`cd 本目录 && python3 -m http.server 8080`，然后打开 <http://localhost:8080>。

## 功能一览

| 功能 | 说明 |
|---|---|
| 学习流程 | 选词库 → 随机抽词（默认 50）→ **浏览模式**逐词学习 → **测验模式**「看单词选英文释义」即时判分 |
| 美式发音 | 每个单词/例句均可发音（🔊 按钮或 `P` 键），优先 Google US English / Samantha / Microsoft Zira |
| 错题本 | 测验答错、浏览标记「没记住」自动收录；按词库分组；到期单词置顶高亮 |
| 记忆曲线 | 艾宾浩斯 8 级调度：20 分钟 → 1 小时 → 9 小时 → 1 天 → 2 天 → 6 天 → 14 天 → 30 天 |
| 复习评级 | 忘记（重置）/ 模糊（×1.2 不升级）/ 记住（下一级）/ 牢记（跳一级）；通过第 8 级自动毕业 🎓 |
| 配置项 | 词量（默认 50）、先浏览/直接测验、浏览顺序、选项数 4/6、浏览自动翻页时长 |
| 快捷键 | `A–F`/`1–6` 答题 · `P` 发音 · `Enter` 下一个 · `←/→` 翻页 · `T` 中文 · `M` 标记 · `X` 没记住 · `Esc` 关弹窗 |
| 弹窗 | Tutorial 使用说明 · 常用词根词缀表 / 常用医学缩略语表 |
| 数据持久化 | 错题本、复习进度、配置存 `localStorage`（键 `vocab_wrongbook_v1` / `vocab_cfg_v1`），关闭重开不丢失 |

## 部署到 GitHub Pages（Mac / iPad 多设备使用）

本项目为纯静态站点，推送 GitHub 后开启 Pages 即可在线使用：

1. GitHub 网页新建**公开**仓库（如 `med-vocab`，不要勾选初始化 README）
2. 推送：
   ```bash
   git remote add origin git@github.com:<用户名>/med-vocab.git
   git push -u origin main
   ```
3. 仓库 **Settings → Pages → Build and deployment → Branch 选 `main` / `(root)` → Save**
4. 约 1 分钟后访问 `https://<用户名>.github.io/med-vocab/`

**iPad / iPhone 使用**：Safari 打开上述网址 → 分享按钮 → **添加到主屏幕**。
本应用已内置 PWA（`manifest.webmanifest` + `sw.js`）：从主屏幕图标启动为全屏独立窗口；
首次在线访问后词库自动缓存，**断网也能使用**（更新应用后需联网打开一次刷新缓存；
若改动了词库，请把 `sw.js` 里的 `CACHE` 版本号递增一位）。

**多设备数据说明**：学习进度存于各设备浏览器的 localStorage，**设备之间不会自动同步**
（Mac 的 Chrome 与 iPad 的 Safari 是两份独立数据）。如需转移进度，可后续在应用内加
「导出 / 导入进度（JSON）」功能。

## 目录结构

```
vocab-app/
├── index.html              # 主应用（双击运行）
├── vocab/
│   ├── manifest.js         # 词库清单（window.VOCAB_MANIFEST，38 条）
│   ├── vocab_*.js          # 19 个核心精选词库（419 词）
│   └── vocab_*-full.js     # 19 个学科全集词库（4403 词）
├── tools/
│   └── convert_vocab.py    # 词表转换工具（docx 表格/段落两种排版 + CSV → vocab JS）
└── README.md
```

## 词条数据格式

每个词条字段（`vocab/vocab_*.js`）：

```js
{
  "word": "Hyperkalemia",            // 术语
  "phonetic": "",                    // 音标（可留空；本项目源数据无音标，UI 自动隐藏）
  "pos": "",                         // 词性（可留空）
  "def_en": "Abnormally high serum potassium…",  // 英文释义（测验选项来源）
  "def_zh": "血钾过高，可致心律失常…",              // 中文解释
  "name_zh": "高钾血症",               // 中文译名
  "example": "", "example_zh": "",   // 例句（可留空，UI 自动隐藏）
  "etymology": "",                   // 词根词缀/记忆法（可留空）
  "tags": ["Cardiovascular System"],
  "audio": ""                        // 可选：本地 mp3 路径；留空用 Web Speech API
}
```

## 新增 / 自定义词库

```bash
# 从 docx 术语表生成（自动识别「表格版」与「段落版」两种排版；--out vocab）
python3 tools/convert_vocab.py --docx "/path/术语表.docx"

# 同一学科第二套词库共存：加 id / 显示名后缀（如全集版）
python3 tools/convert_vocab.py --docx "/path/英中双语.docx" \
    --id-suffix=-full --label-suffix=" · 全集"

# 从 CSV/TSV 追加一个自定义词库（列名支持 word/term、def_en/英文释义、def_zh/中文解释 等）
python3 tools/convert_vocab.py --csv mywords.csv --bank-id mywords --label "我的词库"
```

转换后会在 `vocab/manifest.js` 自动登记（保留已有词库条目、替换同 id 条目）；刷新 `index.html` 即可看到新词库卡片。

## 数据来源

- 核心精选词库：《20_医学专有名词解释_双语术语表.docx》（USMLE Step 1 从零开始 · 双语教科书式讲义 · 2026-10 编排，419 核心术语）
- 学科全集词库：《医学专有名词解释_英中双语.docx》（Kimi_Agent_知识点合并版 · 4403 词条 · 19 学科）
- 知识点基础：USMLE 题库逐题提炼知识点合并；体系参照 First Aid for the USMLE Step 1 (2026, 35th ed.)、Pathoma、Robbins Basic Pathology
- 界面风格：与《USMLE Question Bank — Timed Practice》(index.html, UWorld 风格) 同构——navy 顶栏、卡片布局、Tutor 即时判分
