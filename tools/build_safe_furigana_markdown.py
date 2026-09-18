from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "01 Lessons" / "Lesson001 Business Japanese - Meeting.md"
OUTPUT = ROOT / "01 Lessons" / "Lesson001 商务日语 - 会议 - 安全注音版.md"


READINGS = {
    "日本語能力試験": "にほんごのうりょくしけん",
    "販売計画": "はんばいけいかく",
    "意見交換": "いけんこうかん",
    "関係部署": "かんけいぶしょ",
    "調査結果": "ちょうさけっか",
    "関係者": "かんけいしゃ",
    "参加者": "さんかしゃ",
    "担当者": "たんとうしゃ",
    "参考資料": "さんこうしりょう",
    "会議資料": "かいぎしりょう",
    "今日中": "きょうじゅう",
    "本日中": "ほんじつじゅう",
    "午後三時": "ごごさんじ",
    "新企画": "しんきかく",
    "会議": "かいぎ",
    "確認": "かくにん",
    "資料": "しりょう",
    "日程": "にってい",
    "調整": "ちょうせい",
    "議題": "ぎだい",
    "共有": "きょうゆう",
    "予定": "よてい",
    "内容": "ないよう",
    "連絡": "れんらく",
    "報告": "ほうこく",
    "説明": "せつめい",
    "提案": "ていあん",
    "相談": "そうだん",
    "参加": "さんか",
    "出席": "しゅっせき",
    "欠席": "けっせき",
    "変更": "へんこう",
    "決定": "けってい",
    "案内": "あんない",
    "作成": "さくせい",
    "配布": "はいふ",
    "進捗": "しんちょく",
    "情報": "じょうほう",
    "方針": "ほうしん",
    "質問": "しつもん",
    "整理": "せいり",
    "計画": "けいかく",
    "意見": "いけん",
    "事前": "じぜん",
    "承知": "しょうち",
    "添付": "てんぷ",
    "皆様": "みなさま",
    "場合": "ばあい",
    "明日": "あした",
    "今日": "きょう",
    "本日": "ほんじつ",
    "今後": "こんご",
    "来月": "らいげつ",
    "時間": "じかん",
    "都合": "つごう",
    "結論": "けつろん",
    "修正": "しゅうせい",
}

TITLE_REPLACEMENTS = {
    "# Lesson001 Business Japanese - Meeting": "# Lesson001 商务日语 - 会议",
    "Scene: Business Japanese / Meeting": "场景：商务日语 / 会议",
    "Status:": "状态：",
    "System:": "系统：",
    "Goal:": "目标：",
    "## ① Scene": "## ① 场景介绍",
    "## ② Core Vocabulary": "## ② 核心词汇",
    "## ③ Collocations": "## ③ 固定搭配",
    "## ④ Sentence Pattern": "## ④ 句型表达",
    "## ⑤ Dialogue": "## ⑤ 对话",
    "## ⑥ Japanese Thinking": "## ⑥ 日本人的表达逻辑",
    "## ⑦ Grammar": "## ⑦ 文法",
    "## ⑧ JLPT Analysis": "## ⑧ JLPT 真题分析",
    "## ⑨ Practice": "## ⑨ 练习",
    "## ⑩ Review": "## ⑩ 复习",
    "## Lesson001 Database Items": "## Lesson001 数据库条目",
    "### Vocabulary Card": "### 词汇卡",
    "### Confirmed official source": "### 已确认的官方来源",
    "### Uploaded past papers": "### 已上传真题",
    "### Expected N1 links": "### 预期 N1 关联",
    "### Collocation Practice": "### 固定搭配练习",
    "### Sentence Building": "### 造句练习",
    "### Instant Response": "### 即时应答",
    "### Listening Mini Task": "### 听力小练习",
    "### Reading Mini Task": "### 阅读小练习",
    "### Integrated Practice": "### 综合练习",
}

LABEL_REPLACEMENTS = {
    "Function:": "功能：",
    "Formality:": "正式程度：",
    "Register:": "语域：",
    "Examples:": "例句：",
    "Thinking:": "表达逻辑：",
    "Practice:": "练习：",
    "Answer:": "答案：",
    "Answers:": "答案：",
    "Model answers:": "参考答案：",
    "Model:": "参考写法：",
    "Script:": "听力脚本：",
    "Question:": "问题：",
    "Questions:": "问题：",
    "Key expressions:": "关键表达：",
    "Source:": "来源：",
    "Source status:": "来源状态：",
    "Vocabulary:": "词汇：",
    "Collocations:": "固定搭配：",
    "Grammar:": "文法：",
    "Scene tags:": "场景标签：",
    "JLPT Connection:": "JLPT 关联：",
    "Meeting usage:": "会议场景用法：",
    "Meaning:": "意思：",
    "Text:": "阅读文本：",
    "Day 1": "第 1 天",
    "Day 2": "第 2 天",
    "Day 3": "第 3 天",
    "Week 1": "第 1 周",
    "Month 1": "第 1 个月",
}


KEYS = sorted(READINGS, key=len, reverse=True)


def add_readings(text: str) -> str:
    if not re.search(r"[\u3040-\u30ff]", text):
        return text
    out = []
    i = 0
    while i < len(text):
        key = next((k for k in KEYS if text.startswith(k, i)), None)
        if key:
            reading = READINGS[key]
            explicit = f"{key}（{reading}）"
            if text.startswith(explicit, i):
                out.append(explicit)
                i += len(explicit)
            else:
                out.append(explicit)
                i += len(key)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def localize(line: str) -> str:
    for old, new in TITLE_REPLACEMENTS.items():
        line = line.replace(old, new)
    for old, new in LABEL_REPLACEMENTS.items():
        if line.strip() == old:
            line = line.replace(old, new)
        elif line.startswith(old + " "):
            line = line.replace(old, new, 1)
    return line


def main():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    output = []
    for line in lines:
        line = localize(line)
        line = add_readings(line)
        output.append(line)
    OUTPUT.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
