# english-textbook-reader · 英语教材点读网页生成 Skill

一句话：把"**英语教材页面图片 + 配套录音**"做成可点读的课本网页——逐句切分**原声**、图中热区点读、整课连播 / 跟读 / 暂停 / 单句重复，并可发布成免登录的公开链接。

> 在线示例（北师大版五上 Unit 1 Jobs，GitHub Pages 永久链接）：
> https://aiolosking.github.io/english-tapread/

不绑定任何出版社、年级、单元或本机路径；每次只处理本次提供的材料。

## 这是什么 / 解决什么问题

- **输入**：一个材料目录 = 课本页面图片（jpg/png…）+ 配套录音（mp3/wav…）+ 可选使用说明 txt。
- **输出**：独立成品文件夹内的点读网页（`index.html` + `data.js` + `images/` + `audio/` + `对应表.csv` + `使用说明.md`），可另出单文件版与公开部署链接。
- **核心保证**：声音全部来自教材配套**原录音逐句切分**，不用 AI 合成语音补齐；录音里没有的句子如实标"无音频"，不给假播放按钮。

## 仓库结构

| 路径 | 作用 |
| --- | --- |
| `SKILL.md` | Skill 入口说明（触发条件、流程、硬性约束、部署规则） |
| `scripts/inspect_material.py` | 检查材料目录（图片/音频/使用说明），输出 inspect.json |
| `scripts/asr_words.py` | faster-whisper 词级时间戳 → words.json |
| `scripts/align.py` | 播报脚本与 ASR 贪心顺序对齐 → aligned.json（含每句切片起止） |
| `scripts/build.py` | 按 spec + aligned 生成成品网页、切片音频、对应表 |
| `scripts/build_single.py` | 生成图片/音频 base64 内嵌的单文件版 HTML |
| `scripts/verify.py` | 结构校验 + ASR 抽查切片是否读对 |
| `scripts/publish_anonymous.py` | 免账号、约 3 天有效的公开链接（litterbox 72h） |
| `assets/template.html` | 响应式点读页模板（热区、列表、连播/暂停/重复/跟读、单 audio 防叠音） |
| `references/workflow.md` | Stage 0–7 细节、对应表 schema、对齐启发式、部署清单 |
| `references/pages-spec.md` | spec.json 写法、热区取值与叠图核对、正文/练习/答案区分 |

## 如何使用（作为 Qoder Skill）

1. **安装**：把本仓库克隆或复制到 `~/.qoder/skills/english-textbook-reader/`
   （Windows 即 `C:\Users\<用户名>\.qoder\skills\english-textbook-reader\`）。放入即热加载，无需重启。
2. **调用**：对话里输入 `/english-textbook-reader <材料目录>`，
   或直接说"用 english-textbook-reader 处理 \<目录\> 的图片和音频，做成点读网页"。
3. **材料准备**：目录里放页面图片、配套录音、可选使用说明 txt；缺图或缺音频时 Skill 会先询问，不凭空补。
4. **产出位置**：`<材料目录>/成品/<教材>-<单元>/`，每次运行新建文件夹，**不覆盖已有成品**。
5. **打开使用**：打开成品里的 `index.html`（或单文件版），点图中气泡或右侧句子即读并高亮；
   控制条支持整课连播 / 暂停·继续 / 单句重复 / 跟读 / 停止。

## 如何制作（内部流程 Stage 0–7）

0. **检查**：`inspect_material.py` 盘点图片/音频/页码；读使用说明并遵守其中约束。
1. **读图写规格**：`spec.json`（页、条目、像素热区、答案标注）+ `script.json`（按录音顺序的播报单元，含 heard-but-not-on-page 的播报语）；热区用 ffmpeg 叠图核对后定稿。
2. **ASR**：`asr_words.py --model small` 取词级时间戳（同一音频已有转写可 `--reuse`）。
3. **对齐**：`align.py` 贪心顺序匹配（指针只前进，误听不会打乱后文）；按 kind 设跳过窗、阈值 0.55、切片夹取防止串句；迭代 script 直到未匹配项仅为"录音中确实没有"。
4. **构建**：`build.py` 复制图片、切 mp3（48k 单声道）、写 data.js / index.html / 对应表.csv / 使用说明.md。
5. **校验**：`verify.py` 结构问题必须为 0；`--asr N` 抽查切片；孤立单词 ASR 读不准的列为"无法机器确认"，如实说明、不当作正确。
6. **浏览器实测**：点读高亮、连播跨页、暂停/继续（含跟读停顿中暂停）、单句重复、切句停旧音、停止；并看手机/平板宽度布局。
7. **部署**（仅当用户要求）：默认免账号 ~3 天链接（`build_single.py` → `publish_anonymous.py --time 72h`）；或 GitHub 仓库 + Pages 等长期托管。

## 硬性保证

- 逐句切分原录音：保留完整首尾、不混入下一句；不照搬其他教材的时间标记。
- 禁止 AI 合成语音补齐；无音频/无法确认的句子标"无音频"。
- 保留可检查可修改的**对应表**（对应表.csv / aligned.json）：文字、页码、图中位置、原音频、起止时间、核对状态。
- 热区按百分比定位，缩放/换屏后仍准确。
- 单 `<audio>` 元素复用，切换句子先停旧音，绝不叠音。

## 依赖

- python3、ffmpeg / ffprobe（切分与叠图核对）
- faster-whisper（`pip install faster-whisper`，CPU int8）用于对齐与抽查

## 部署规则

- 优先已配置好的托管；没有则明确告知缺哪个账号/token 并停下；付费前先征得同意。
- 账号密钥绝不写进 Skill、网页或公开文件。
- 本地地址、临时预览、"上传成功"都不算部署成功；须用**未登录浏览器**打开真实 HTTPS 网址，确认图片与音频可加载、手机/平板布局正常，才交付链接。
- 发布失败或证书未就绪：保留成品与发布记录，说明阻碍，不宣称完成。

## 版权

教材图片与配套录音版权归原作者 / 出版社所有；本 Skill 及其成品仅用于个人与家庭学习，不作商业用途。
