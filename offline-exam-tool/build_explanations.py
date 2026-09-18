#!/usr/bin/env python3
"""Build quality-checked explanations for the latest ten N1 periods."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import build_offline_exam as builder
from vocab_explanation_details import CONTEXT, SYNONYM, USAGE
from grammar_explanation_details import DETAILS as GRAMMAR_DETAILS, ORDERINGS


TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
OUTPUT_DIR = TOOL_DIR / "explanations"
TARGET_PERIODS = [
    "2025.12", "2025.07", "2024.12", "2024.07", "2023.12",
    "2023.07", "2022.12", "2022.07", "2021.12", "2021.07",
]
SOURCE_GLOBS = {
    "2024.07": "2024年7月__【1】*答案解析+听力原文+译文.md",
    "2023.12": "2023年12月__【2】*答案解析+译文.md",
    "2023.07": "2023年7月__【3】*答案解析+听力原文+译文.md",
}
DETAILED_READING_SOURCE_GLOBS = {
    # This OCR copy contains the option-by-option reading explanations that are
    # absent from the cleaner 17-page translation copy.  It is used only after
    # answer-number and content-quality checks below.
    "2023.12": "2023年12月__【1】*答案解析+听力原文.md",
}
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
ANSWER_MARKER = re.compile(r"(?m)^\s*(\d{1,2})\s*[、．.]?\s*正解\s*[：:]\s*([1-4])")
NUMBERED_MARKER = re.compile(r"(?m)^\s*(\d{1,2})\s*[、．.]?\s*(?=\S)")


# Detailed reading notes for every 問題1 item whose source explanation is AI.
# Each note explicitly distinguishes a real homophone/other word from a
# nonstandard distractor, so a wrong choice remains useful vocabulary data.
READING_DETAILS: dict[str, dict[str, Any]] = {
    "markdown-2025.12-language-1": {"notes": [
        "正确。頑丈（がんじょう）：结实、坚固。", "是实际存在的读音，可对应「感情」「勘定」「環状」等词，但不是「頑丈」。",
        "通常不存在对应的现代常用词；它把「じょう」的长音省掉了。", "可对应「官女（かんじょ）」等词，但不是「頑丈」，同时缺少长音。"],
        "comment": "「頑」在这里读がん，「丈」读じょう；常见错误是把首音清化，或漏掉「う」表示的长音。"},
    "markdown-2025.12-language-2": {"notes": [
        "是「及んで（およんで）」的实际读音，表示达到、涉及，但字形不是「潜んで」。", "是「絡んで（からんで）」的实际读音，表示缠绕、牵涉。",
        "是「沈んで（しずんで）」的实际读音，表示下沉、消沉。", "正确。潜んで（ひそんで）：潜藏、隐藏。"],
        "comment": "「潜む」是训读ひそむ；不要仅凭“潜入”的音读せん去猜，活用后为「潜んで」。"},
    "markdown-2025.12-language-3": {"notes": [
        "不是「行政」的读音；作为音串在现代常用词中也不常单独使用。", "是实际存在的读音，可对应「構成」「公正」「更生」等大量词，但不是「行政」。",
        "通常不存在对应的现代常用词，也不是「行政」的规范读音。", "正确。行政（ぎょうせい）：国家或地方公共团体实施的公共事务管理。"],
        "comment": "「行」在行政、行事、行列等词中常读ぎょう；「政」读清音せい，不读ぜい。"},
    "markdown-2025.12-language-4": {"notes": [
        "是「超越（ちょうえつ）」的实际读音，但「卓越」的首字不读ちょう。", "正确。卓越（たくえつ）：远远高出一般水平。",
        "是「択一（たくいつ）」的实际读音，但不是「卓越」。", "通常不存在对应的现代常用词；混合了「超越」的首音和「択一」的尾音。"],
        "comment": "把「卓越」与高频词「超越（ちょうえつ）」混读是典型错误；应固定记作たくえつ。"},
    "markdown-2025.12-language-5": {"notes": [
        "是「相応しく（ふさわしく）」的实际读音，表示相称、合适。", "是「宜しく（よろしく）」的实际读音，常表示适当地、请多关照。",
        "正确。芳しくない（かんばしくない）：情况不理想、不佳。", "是「著しく（いちじるしく）」的实际读音，表示显著地。"],
        "comment": "「芳しい」读かんばしい，否定形「芳しくない」常用于成绩、业绩、评价等“不理想”。"},
    "markdown-2025.12-language-6": {"notes": [
        "通常不存在对应的现代常用词；把「轄」误浊化成がつ。", "正确。管轄（かんかつ）：在权限范围内管理、支配。",
        "かんかい是实际存在的读音，可对应「官界」「感懐」「寛解」等词，但不是「管轄」。", "かんがい是实际存在的读音，可对应「感慨」「灌漑」等词，但不是「管轄」。"],
        "comment": "「轄」在管轄、所轄、直轄中都读かつ；不要受后续浊音或相近词影响读成がつ。"},
    "markdown-2025.07-language-1": {"notes": [
        "ようか是实际存在的读音，最常见写作「八日」，但不是「余暇」。", "正确。余暇（よか）：工作、学习之外的空闲时间。",
        "通常不存在对应的现代常用词，也不是「余暇」的规范读音。", "是「洋画（ようが）」的实际读音，表示西洋画或西方电影。"],
        "comment": "「余暇」两个汉字都取短音：よ＋か。常见干扰是擅自补长音，或把「暇」浊化为が。"},
    "markdown-2025.07-language-2": {"notes": [
        "是「鋭い（するどい）」的实际读音，表示锋利、敏锐，语义上常与鈍い相反。", "正确。鈍い（にぶい）：迟钝、不灵敏；也可表示颜色或声音不鲜明。",
        "是「粗い／荒い（あらい）」的实际读音，表示粗糙或粗暴。", "是「危うい（あやうい）」的实际读音，表示危险、险些。"],
        "comment": "「鈍い」在“动作迟缓、感觉迟钝”时读にぶい；注意不要与反义词「鋭い」混淆。"},
    "markdown-2025.07-language-3": {"notes": [
        "是「譴責（けんせき）」的实际读音，表示严厉责备或纪律处分。", "是「検疫（けんえき）」的实际读音，表示检疫。",
        "是「建設（けんせつ）」的实际读音，表示建设。", "正确。検閲（けんえつ）：检查出版物、通信等内容。"],
        "comment": "四项都是实际词语的读音；关键是区分第二个汉字：責＝せき、疫＝えき、設＝せつ、閲＝えつ。"},
    "markdown-2025.07-language-4": {"notes": [
        "正确。崇高（すうこう）：高尚、崇高。", "是实际存在的读音，可对应「修好」「就航」「周航」等词，但不是「崇高」。",
        "是实际存在的读音，可对应「昇降」「商工」「症候」等词，但不是「崇高」。", "是实际存在的读音，可对应「走行」「装甲」「奏功」等词，但不是「崇高」。"],
        "comment": "「崇」在崇高、崇拝中读すう。其余选项都是高频同音词群，不能只凭熟悉感选择。"},
    "markdown-2025.07-language-5": {"notes": [
        "是「暴く（あばく）」的实际读音，表示揭露、揭发。", "是「貫く（つらぬく）」的实际读音，表示贯穿、贯彻。",
        "是「欺く（あざむく）」的实际读音，表示欺骗。", "正确。裁く（さばく）：审判、裁决或妥善处理。"],
        "comment": "四项都是实际动词；这类题要把汉字与整组训读绑定记忆：暴く、貫く、欺く、裁く。"},
    "markdown-2025.07-language-6": {"notes": [
        "是「今日中（きょうじゅう）」的实际读音，表示今天之内。", "是「宮中（きゅうちゅう）」的实际读音，表示皇宫之中。",
        "正确。胸中（きょうちゅう）：内心、心中。", "是「九十（きゅうじゅう）」的实际读音。"],
        "comment": "四项都能形成实际词语；区分「胸＝きょう／宮＝きゅう」以及「中＝ちゅう／十＝じゅう」的清浊音。"},
    "jlpt4you-2024.12-vocabulary-1-1": {"notes": [
        "是「説教（せっきょう）」的实际读音，表示说教、训诫。", "正确。絶叫（ぜっきょう）：大声喊叫、尖叫。",
        "通常不存在对应的现代常用词；把「叫」误读为きゅう。", "是「接球（せっきゅう）」的实际读音，指接住来球。"],
        "comment": "「絶」在熟语中常促音化为ぜっ；「叫」在絶叫、叫喚中读きょう，不读きゅう。"},
    "jlpt4you-2024.12-vocabulary-1-2": {"notes": [
        "正确。背後（はいご）：背后、后方。", "是「廃校（はいこう）」等词的实际读音，但不是「背後」。",
        "是「生後（せいご）」的实际读音，表示出生以后。", "是「成功（せいこう）」等词的实际读音，但不是「背後」。"],
        "comment": "「背」在背後、背景中常读はい；「後」在这个音读熟语中读ご，不读こう。"},
    "jlpt4you-2024.12-vocabulary-1-3": {"notes": [
        "正确。抱負（ほうふ）：对未来的志向、决心。", "通常不存在对应的现代常用词；末尾把ふ误浊化为ぶ。",
        "是旧称「保父（ほふ）」的实际读音，过去指男性保育员，但不是「抱負」。", "通常不存在对应的现代常用词，同时误省长音并误浊化。"],
        "comment": "「抱」取音读ほう，「負」读ふ；需同时保留长音う，并保持ふ为清音。"},
    "jlpt4you-2024.12-vocabulary-1-4": {"notes": [
        "是「からかって」的实际读音，通常写作「揶揄って」，表示戏弄。", "是「罵って（ののしって）」的实际读音，表示辱骂。",
        "正确。侮って（あなどって）：轻视、小看。", "是「裏切って（うらぎって）」的实际读音，表示背叛。"],
        "comment": "四项都是实际动词的て形；「侮る」是易错训读，词干为あなどり，促音后为あなどって。"},
    "jlpt4you-2024.12-vocabulary-1-5": {"notes": [
        "一般词汇中不存在这一标准读法；属于把「筋」机械音读为きん的干扰。", "一般词汇中不存在这一标准读法；前半虽读对，后半把みち误作どう。",
        "一般词汇中不存在这一标准读法；两个汉字都被机械替换了读音。", "正确。筋道（すじみち）：事物的条理、合乎逻辑的顺序。"],
        "comment": "「筋道」是训读组合すじ＋みち。熟字看似可音读时，仍要以固定词汇读法为准。"},
    "jlpt4you-2024.12-vocabulary-1-6": {"notes": [
        "标准辞书中通常不作为现代常用词读音出现，也不是「奔放」。", "标准辞书中通常不存在这一常用读音；首音与半浊音均为干扰。",
        "正确。奔放（ほんぽう）：不受拘束、自由豪放。", "是「万邦／万法（ばんぽう）」等词的实际读音，但不是「奔放」。"],
        "comment": "「奔」读ほん，「放」在此发生半浊音化读ぽう；常见错误是把ほん误成はん／ばん，或把ぽう误成ほう。"},
}


def compact(value: Any, limit: int = 140) -> str:
    text = str(value or "").replace(builder.UNDERLINE_OPEN, "").replace(builder.UNDERLINE_CLOSE, "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def expected_answers(question: dict[str, Any]) -> list[int]:
    raw = str(question.get("rightAnswer") or "")
    if question.get("qaType") == 4 and int(question.get("rightAnswer") or 0) > 9:
        return [int(char) for char in raw]
    return [int(question.get("rightAnswer") or 0)]


def correct_option(question: dict[str, Any]) -> str:
    answers = expected_answers(question)
    options = question.get("options") or []
    values = [compact(options[index - 1]) for index in answers if 0 < index <= len(options)]
    return "；".join(value for value in values if value) or "对应选项"


def evidence_sentence(question: dict[str, Any], option: str) -> str:
    source = "\n".join(str(question.get(key) or "") for key in ("passage", "question", "title", "subQuestion"))
    sentences = [compact(item, 170) for item in re.split(r"(?<=[。！？!?])|\n+", source) if len(compact(item)) >= 12]
    target = {char for char in option if re.match(r"[一-龥ぁ-んァ-ヶ]", char)}
    if not target or not sentences:
        return ""
    scored = [(len(target & set(sentence)), -len(sentence), sentence) for sentence in sentences]
    score, _, sentence = max(scored)
    return sentence if score >= 2 else ""


def grammar_role(value: Any) -> str:
    """Describe the main grammatical job of an option for concrete contrasts."""
    text = compact(value, 240)
    rules = [
        (("仮に",), "假设性前提，通常需要与条件表达呼应"),
        (("今にも",), "眼看马上发生，通常与「そうだ」等样态表达呼应"),
        (("とても",), "与否定呼应，表示无论如何也做不到"),
        (("まもなく",), "客观时间上的“不久、即将”"),
        (("をはじめ",), "以某个代表项目为首进行列举"),
        (("とあって",), "由于处于特殊情况而自然产生后项结果"),
        (("うえで",), "在做前项时或以其为前提"),
        (("わりに",), "结果与按前项标准作出的预想不相称"),
        (("とするには",), "要把对象判定、认定为前项所述状态"),
        (("となるには",), "要变化并成为某种身份或状态"),
        (("とは",), "引用内容并常带惊讶、定义或评价语气"),
        (("悩ませ",), "主动使别人烦恼；施事者是造成困扰的一方"),
        (("悩まされ",), "被动地受某事困扰；主语是承受影响的一方"),
        (("勢いだ",), "动作或趋势强劲发展的势头"),
        (("ことは否めない",), "无法否认某一事实"),
        (("見込みだ",), "基于依据作出的预期或可能性判断"),
        (("してくれた",), "对方为我方做事；在抱怨语境中可构成反语"),
        (("しかねない",), "有可能导致通常不希望出现的结果"),
        (("らしい",), "符合该身份典型特征，或根据消息作推定"),
        (("みたい",), "口语比况，表示像……一样或举例"),
        (("てばかりもいられない", "でばかりもいられない"), "不能一直停留在某动作或状态"),
        (("なくしては", "ない限り", "ないことには"), "必要条件（若不满足前项，后项便不成立）"),
        (("くらいなら",), "取舍比较（与其做前项，不如选择后项）"),
        (("に越したことはない",), "最佳选择（没有比……更好）"),
        (("わけがない", "はずがない"), "有根据的强烈否定或不可能"),
        (("ざるを得ない",), "受情势所迫而不得不做"),
        (("ものの", "ながらも", "反面", "とはいえ"), "让步转折（虽有前项，仍出现相反后项）"),
        (("どころか",), "递进反转（不但不是前项，反而达到更强后项）"),
        (("せい", "ばかりに", "がゆえに"), "原因及其结果，通常带负面或强因果语感"),
        (("あげく", "始末"), "经过过程后落到不理想结果"),
        (("以上", "からには"), "既然前提成立，后项便有相应判断或责任"),
        (("なり",), "前一动作发生后立刻出现后一动作"),
        (("次第",), "前项一完成便马上实施后项"),
        (("に限って",), "偏偏在特定时候发生反常情况"),
        (("に反して",), "结果与预想、意愿或规定相反"),
        (("にあって", "において"), "限定所处时代、场合或领域"),
        (("を機に", "に際して"), "以事件为契机或在其发生之际"),
        (("のみならず", "ばかりか"), "递进追加（不只前项，而且后项）"),
        (("かもしれない", "見込み", "恐れがある"), "可能性或预测"),
        (("ように", "ために", "べく"), "目的或为实现目标采取的方式"),
        (("てはいられない",), "受情势限制，不能继续维持该动作或状态"),
        (("こそ",), "突出并强调前接成分"),
        (("しか",), "与否定呼应，表示除此之外没有其他范围"),
        (("そう", "ようだ", "みたい"), "根据迹象作出的样态判断或比况"),
        (("ていただ", "てくださ", "お越し", "見えました"), "授受或敬语关系"),
        (("たら", "なら", "れば", "としても", "とすると"), "条件、假定或反事实设想"),
        (("ので", "ため", "から"), "原因理由"),
        (("が", "けれど", "のに"), "前后转折或逆接"),
        (("だけ", "のみ"), "范围限定"),
    ]
    for needles, description in rules:
        if any(needle in text for needle in needles):
            return description
    return "该选项自身所表示的接续关系和语气"


def generated_explanation(category: str, question: dict[str, Any]) -> str:
    answer = "、".join(map(str, expected_answers(question)))
    option = correct_option(question)
    group = int(question.get("groupNumber") or 0)
    correct = set(expected_answers(question))
    options = question.get("options") or []

    def option_lines(correct_reason: str, wrong_reason: str) -> list[str]:
        lines = []
        for index, label in enumerate(options, 1):
            choice = compact(label, 180)
            if index in correct:
                lines.append(f"选项 {index}（正确）「{choice}」：{correct_reason}")
            else:
                lines.append(f"选项 {index}「{choice}」：{wrong_reason}")
        return lines

    def without_repeated_label(label: Any, note: Any) -> str:
        choice = compact(label, 180)
        detail = str(note).strip()
        prefix = f"{choice}："
        return detail[len(prefix):].lstrip() if detail.startswith(prefix) else detail

    heading = ["【AI 生成解析】", f"正确答案：{answer}「{option}」"]
    reading_details = READING_DETAILS.get(str(question.get("id") or ""))
    if category == "文字" and reading_details:
        notes = list(reading_details.get("notes") or [])
        if len(notes) != len(options):
            raise ValueError(f"{question.get('id')}: reading explanation count does not match options")
        lines = heading[:]
        for index, (label, note) in enumerate(zip(options, notes), 1):
            correct_mark = "（正确）" if index in correct else ""
            lines.append(f"选项 {index}{correct_mark}「{compact(label, 180)}」：{without_repeated_label(label, note)}")
        comment = compact(reading_details.get("comment"), 500)
        if comment:
            lines.append(f"【AI 点评】{comment}")
        return "\n".join(lines)
    if category == "文字":
        return "\n".join(heading + option_lines(
            "这是题干标出词在本句中的规范读音。",
            "不是该词在此处的规范读音，属于音读、训读、浊音或长短音干扰。",
        ))
    context_details = CONTEXT.get(str(question.get("id") or ""))
    if category == "词汇" and group == 2 and context_details:
        notes, comment = context_details
        if len(notes) != len(options):
            raise ValueError(f"{question.get('id')}: context explanation count does not match options")
        lines = heading[:]
        for index, (label, note) in enumerate(zip(options, notes), 1):
            correct_mark = "（正确）" if index in correct else ""
            lines.append(f"选项 {index}{correct_mark}「{compact(label, 180)}」：{without_repeated_label(label, note)}")
        lines.append(f"【AI 点评】{comment}")
        return "\n".join(lines)
    if category == "词汇" and group == 2:
        return "\n".join(heading + option_lines(
            "代入后词义、词性和固定搭配都符合上下文。",
            "代入后在语义范围、词性或搭配对象上不符合本句。",
        ))
    synonym_details = SYNONYM.get(str(question.get("id") or ""))
    if category == "词汇" and group == 3 and synonym_details:
        target_meaning, notes, comment = synonym_details
        if len(notes) != len(options):
            raise ValueError(f"{question.get('id')}: synonym explanation count does not match options")
        lines = heading + [f"题干词义：{target_meaning}"]
        for index, (label, note) in enumerate(zip(options, notes), 1):
            correct_mark = "（正确）" if index in correct else ""
            lines.append(f"选项 {index}{correct_mark}「{compact(label, 180)}」：{without_repeated_label(label, note)}")
        lines.append(f"【AI 点评】{comment}")
        return "\n".join(lines)
    if category == "词汇" and group == 3:
        return "\n".join(heading + option_lines(
            "与题干标出的表达在此语境中的核心含义最接近。",
            "与原表达的核心含义、语域或使用范围不一致。",
        ) + ["【AI 点评】近义替换还要同时比较语域、褒贬色彩和搭配。"])
    usage_details = USAGE.get(str(question.get("id") or ""))
    if category == "词汇" and group == 4 and usage_details:
        target_meaning, notes, comment = usage_details
        if len(notes) != len(options):
            raise ValueError(f"{question.get('id')}: usage explanation count does not match options")
        lines = heading + [f"目标词义：{target_meaning}"]
        for index, (label, note) in enumerate(zip(options, notes), 1):
            correct_mark = "（正确）" if index in correct else ""
            lines.append(f"选项 {index}{correct_mark}「{compact(label, 180)}」：{note}")
        lines.append(f"【AI 点评】{comment}")
        return "\n".join(lines)
    if category == "词汇":
        return "\n".join(heading + option_lines(
            "该例句符合这个词的常用含义、搭配对象和句法位置。",
            "该例句在词义、搭配对象或句法位置上至少有一项不自然。",
        ) + ["【AI 点评】用法题不能只对照中文释义，还要检查日语中的固定搭配。"])
    if category == "语法" and group == 6:
        order = ORDERINGS.get(str(question.get("id") or ""))
        if order:
            ordered = [compact(options[int(number) - 1], 180) for number in order]
            return "\n".join(heading + [
                f"正确排序：{' → '.join(order)}",
                f"排序内容：{' ｜ '.join(ordered)}",
                "【AI 点评】先按固定句型、助词接续和修饰关系还原整句；★答案只表示星号所在格，完整顺序以上述排序为准。",
            ])
        return "\n".join(heading + ["正确排序资料暂缺，不能仅凭★答案反推出完整顺序。"])
    if category == "语法":
        detailed = GRAMMAR_DETAILS.get(str(question.get("id") or ""))
        if detailed and str(detailed.get("text") or "").strip():
            return str(detailed["text"]).strip()
        required_role = grammar_role(option)
        lines = heading + [f"本句要求：{required_role}。"]
        for index, label in enumerate(options, 1):
            choice = compact(label, 180)
            role = grammar_role(choice)
            if index in correct:
                reason = f"正确。该项表达{role}，并能与题干前后成分构成完整句意。"
            elif role != required_role:
                reason = f"错误点：该项主要表达{role}；本句需要的是{required_role}，代入后会改写前后逻辑。"
            else:
                reason = f"错误点：虽然同属{role}，但「{choice}」的固定接续、时态或语气不能同时承接题干前后成分。"
            lines.append(f"选项 {index}{'（正确）' if index in correct else ''}「{choice}」：{reason}")
        return "\n".join(lines + ["【AI 点评】判断时同时核对接续形式与前后逻辑；意思相近但接续方向不同也不能替换。"])
    if category == "阅读":
        evidence = evidence_sentence(question, option)
        support = f"文中可定位到：“{evidence}”" if evidence else "应以原文的主旨、指代关系和限定条件为依据"
        return "\n".join(heading + [f"定位依据：{support}。"] + option_lines(
            "与原文的主旨、指代关系和限定条件一致。",
            "与原文相比存在范围扩大、条件遗漏、因果倒置或无依据推断。",
        ))
    if category == "听力":
        return "\n".join(heading + option_lines(
            "对应对话中的最终决定、行动要求或核心态度。",
            "属于对话中被否定、未采用或偏离核心问题的信息。",
        ) + ["【AI 点评】重点听转折后的结论，并区分“提到过”与“最终采用”。"])
    return "\n".join(heading + option_lines("符合题干条件和上下文。", "不符合题干条件或上下文。"))


def clean_source_chunk(chunk: str) -> str:
    lines = []
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("```", "<a id=", "## PDF Page", "- Source locator", "- Extraction method", "- Detected problem")):
            continue
        if re.fullmatch(r"問題\s*\d+", stripped) or re.fullmatch(r"\d+", stripped):
            continue
        lines.append(stripped)
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in lines)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    if len(text) > 4500:
        text = text[:4500].rstrip() + "…"
    return text


def numbered_source_chunks(text: str) -> dict[int, str]:
    """Extract globally numbered 26–66 explanations from clean text-layer PDFs."""
    normalized = text.translate(FULLWIDTH_DIGITS)
    markers = [marker for marker in NUMBERED_MARKER.finditer(normalized) if 26 <= int(marker.group(1)) <= 66]
    chunks: dict[int, str] = {}
    for index, marker in enumerate(markers):
        number = int(marker.group(1))
        if number in chunks:
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else min(len(normalized), marker.start() + 5000)
        chunk = clean_source_chunk(normalized[marker.start():end])
        # Questions 26–35 should contain a translation and four option notes;
        # 36–40 should contain the source's complete ordering and reasoning.
        if 26 <= number <= 35:
            circled = {1: "①", 2: "②", 3: "③", 4: "④"}
            option_notes = sum(
                bool(re.search(fr"(?m)^\s*(?:{index}[.、]?|{circled[index]})\s*\S", chunk))
                for index in range(1, 5)
            )
            if len(chunk) < 120 or option_notes < 4:
                continue
        elif 36 <= number <= 40:
            if not any(label in chunk for label in ("答案", "正解")) or "思路" not in chunk:
                continue
        else:
            continue
        chunks[number] = chunk
    return chunks


def clean_detailed_ocr_chunk(chunk: str) -> str:
    """Keep the readable Chinese reasoning while removing broken OCR citations."""
    text = chunk
    suspicious = "℃№丿乇矿扫扎圭毛旭"
    for opener, closer in (("（", "）"), ("(", ")")):
        pattern = re.escape(opener) + r"[^" + re.escape(closer) + r"]{0,500}" + re.escape(closer)
        text = re.sub(pattern, lambda match: "" if any(char in match.group(0) for char in suspicious) else match.group(0), text)
    text = re.sub(r"\s+", " ", text).strip()
    corrections = {
        "能力能力": "能力", "监视者者": "监视者", "不不会": "不会",
        "本质是是山人类而使用的工具": "本质仍是由人类使用的工具",
        "排 ] 除": "排除", "IOKG": "10KG", "延边尽": "延迟，",
        "该该": "该", "自自己": "自己", "研宄": "研究",
    }
    for broken, fixed in corrections.items():
        text = text.replace(broken, fixed)
    text = re.sub(r"\s*(选项\s*[1-4])\s*", r"\n\1", text)
    text = re.sub(r"\s*(故(?:选择|选项)|因此(?:选择|选项)|由此可知)\s*", r"\n\1", text)
    return text[:4500].rstrip()


def detailed_reading_source_explanations(year: str, exam: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    pattern = DETAILED_READING_SOURCE_GLOBS.get(year)
    if not pattern:
        return {}
    matches = list((ROOT / "output" / "library2_after_2021_markdown").glob(pattern))
    if not matches:
        return {}
    raw = matches[0].read_text(encoding="utf-8").translate(FULLWIDTH_DIGITS)
    fence = "`" * 3
    parts = raw.split(fence)
    blocks = [parts[index].removeprefix("text").strip() for index in range(1, len(parts), 2)]
    # The first eight pages are language/reading explanations; page nine starts
    # the listening transcript and uses a different numbering scheme.
    text = "\n".join(blocks[:8])
    cjk = r"\u3400-\u9fff\u3040-\u30ff"
    for _ in range(4):
        text = re.sub(fr"(?<=[{cjk}0-9])\s+(?=[{cjk}0-9])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    # Four question numbers were misread consistently in this source.
    text = re.sub(r"4\s*&\s*问题是", "48.问题是", text, count=1)
    text = re.sub(r"5\s*&\s*问题是", "58.问题是", text, count=1)
    text = text.replace("问题是 ： 关于写小说的所需条件", "61.问题是：关于写小说的所需条件", 1)
    text = re.sub(r"6\s*生\s*问题是", "64.问题是", text, count=1)
    markers = list(re.finditer(r"(?<!\d)(4[1-9]|5\d|6[0-6])\s*[．.、，,]?\s*", text))
    # A sorting answer ending in 4132 creates a false early '41'; use the last
    # occurrence for each global reading number.
    selected = {int(marker.group(1)): marker for marker in markers}
    ordered = sorted(selected.items(), key=lambda item: item[1].start())
    by_number: dict[int, str] = {}
    for index, (number, marker) in enumerate(ordered):
        if not 41 <= number <= 66:
            continue
        end = ordered[index + 1][1].start() if index + 1 < len(ordered) else len(text)
        chunk = clean_detailed_ocr_chunk(text[marker.start():end])
        if len(chunk) < 90 or chunk.count("选项") < 2 or not any(token in chunk for token in ("正确", "符合", "选择", "排除")):
            continue
        by_number[number] = chunk
    questions = {
        int(question["number"]): question
        for category in ("语法", "阅读") for question in exam[category]
        if str(question.get("number", "")).isdigit()
    }
    return {questions[number]["id"]: chunk for number, chunk in by_number.items() if number in questions}


def source_explanations(year: str, exam: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    pattern = SOURCE_GLOBS.get(year)
    if not pattern:
        return {}
    matches = list((ROOT / "output" / "library2_after_2021_markdown").glob(pattern))
    if not matches:
        return {}
    text = matches[0].read_text(encoding="utf-8", errors="replace").translate(FULLWIDTH_DIGITS)
    markers = [match for match in ANSWER_MARKER.finditer(text) if 1 <= int(match.group(1)) <= 25]
    chunks: dict[int, tuple[int, str]] = {}
    for index, marker in enumerate(markers):
        number = int(marker.group(1))
        if number in chunks:
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else min(len(text), marker.start() + 2500)
        chunks[number] = (int(marker.group(2)), clean_source_chunk(text[marker.start():end]))

    questions = {
        int(question["number"]): question
        for category in ("文字", "词汇") for question in exam[category]
        if str(question.get("number", "")).isdigit() and int(question["number"]) <= 25
    }
    accepted: dict[str, str] = {}
    for number, question in questions.items():
        found = chunks.get(number)
        if not found:
            continue
        source_answer, chunk = found
        expected = expected_answers(question)[0]
        visible = len(re.findall(r"[一-龥ぁ-んァ-ヶA-Za-z]", chunk))
        if source_answer != expected or len(chunk) < 45 or visible < 30 or "�" in chunk:
            continue
        accepted[question["id"]] = chunk
    numbered = numbered_source_chunks(text)
    all_questions = {
        int(question["number"]): question
        for category in ("语法", "阅读") for question in exam[category]
        if str(question.get("number", "")).isdigit()
    }
    for number, chunk in numbered.items():
        question = all_questions.get(number)
        # The 2023.07 PDF gives a filled sentence that conflicts with the
        # verified answer for Q32 and Q33. Do not import those two chunks.
        known_bad_source = year == "2023.07" and number in {32, 33}
        if question and not known_bad_source:
            accepted[question["id"]] = chunk
    accepted.update(detailed_reading_source_explanations(year, exam))
    return accepted


def build() -> dict[str, Any]:
    data = builder.build()
    # Read Shaobing once without explanation overlays. Otherwise a previously
    # generated fallback can hide a usable scraped explanation on the next run.
    _, raw_shaobing_exams = builder.build_shaobing()
    raw_shaobing_by_id = {
        question["id"]: question
        for categories in raw_shaobing_exams.values()
        for questions in categories.values()
        for question in questions
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"periods": {}, "targetPeriods": TARGET_PERIODS}
    for year in TARGET_PERIODS:
        exam = data["exams"][year]
        # The four Shaobing periods already contain source explanations. Keep good
        # ones and replace only entries that fail the same minimum quality gate.
        if year not in builder.JLPT4YOU_YEARS and year not in builder.MARKDOWN_EXAMS:
            total = sum(len(questions) for questions in exam.values())
            items: dict[str, dict[str, str]] = {}
            source_count = 0
            for category, questions in exam.items():
                for question in questions:
                    detailed = GRAMMAR_DETAILS.get(str(question.get("id") or "")) if category == "语法" else None
                    if detailed and int(question.get("groupNumber") or 0) != 6:
                        items[question["id"]] = {
                            "text": str(detailed["text"]).strip(),
                            "source": str(detailed.get("source") or "Gemini 逐项语法解析"),
                        }
                        continue
                    raw_question = raw_shaobing_by_id.get(question["id"], question)
                    analysis = str(raw_question.get("analysis") or "").strip()
                    useful_audio_source = (
                        category == "听力"
                        and len(analysis) >= 20
                        and sum(char.isdigit() for char in analysis) >= 3
                    )
                    if (len(analysis) >= 35 or useful_audio_source) and "�" not in analysis and "AI 生成" not in str(raw_question.get("analysisSource") or ""):
                        source_count += 1
                        if useful_audio_source and len(analysis) < 35:
                            items[question["id"]] = {
                                "text": "【原附带解析】\n" + analysis,
                                "source": "烧饼日语附带解析（仅整理格式）",
                            }
                    else:
                        items[question["id"]] = {
                            "text": generated_explanation(category, question),
                            "source": "AI 生成（原附带解析未通过质量检查）",
                        }
            payload = {"version": 1, "year": year, "items": items}
            (OUTPUT_DIR / f"{year}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report["periods"][year] = {"total": total, "source": source_count, "generated": total - source_count}
            continue
        source_items = source_explanations(year, exam)
        items: dict[str, dict[str, str]] = {}
        for category, questions in exam.items():
            for question in questions:
                detailed = GRAMMAR_DETAILS.get(str(question.get("id") or "")) if category == "语法" else None
                if detailed and int(question.get("groupNumber") or 0) != 6:
                    items[question["id"]] = {
                        "text": str(detailed["text"]).strip(),
                        "source": str(detailed.get("source") or "Codex 逐题语法解析"),
                    }
                elif question["id"] in source_items:
                    items[question["id"]] = {
                        "text": source_items[question["id"]],
                        "source": "本地答案解析资料（答案与文本质量校验通过）",
                    }
                else:
                    items[question["id"]] = {
                        "text": generated_explanation(category, question),
                        "source": "AI 生成（依据题干、选项与标准答案）",
                    }
        payload = {"version": 1, "year": year, "items": items}
        (OUTPUT_DIR / f"{year}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report["periods"][year] = {
            "total": len(items), "source": len(source_items), "generated": len(items) - len(source_items)
        }
    (OUTPUT_DIR / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = build()
    for period, counts in result["periods"].items():
        print(f"{period}: {counts['total']} questions, source={counts['source']}, generated={counts['generated']}")
