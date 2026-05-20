"""CCVO (Consonant Cluster + Vowel Openness) singability metric.

Faithful port of Štěpánková & Rosa (2025) `consonant_clusters_vowel_openness`
(stepankovab/Computational-Interpretation-of-the-Pentathlon-Principle), used in
Liu et al. (2026, EACL-SRW) as the strongest automatic predictor of human MOS
on singable lyric translation (r = 0.838 with MOS).

Per syllable we emit:
  - cluster marker: C if (trailing consonants of previous syllable +
    leading consonants of this syllable) >= 3, else N;
  - vowel marker: OO (open), VO (mid), VV (close).
A final cluster marker is appended (C if final consonants >= 3, else N).

Distance is Levenshtein(ccvo_src, ccvo_tgt) / min(|ccvo_src|, |ccvo_tgt|),
averaged across paired lines (S&R 2025, lines 270-272).
"""

from __future__ import annotations

import itertools
import re

import eng_to_ipa
import Levenshtein

# IPA consonants (S&R 2025 base set, extended to cover en + zh IPA glyphs).
_CONSONANTS = set("bcdfghjkmnpqstvwxzðňŋɟɡɣɦʔɲʃʒʤʧθřɹɥɻɽɾɢɫɬɮɱɳɴɸβʁʕʝçχɧɕʑʐʈɖʂɭɲ")

# Vowel openness groups (S&R 2025 + cross-lingual extension for en/zh).
_OPEN = set("aæáāɑäɐɒ")
_MID = set("əeoéóɔɛøœɵɤʌɞɜɚɝ")
_CLOSE = set("iuyíúýɪʊɨʉɯ")

_STRIP = re.compile(r"[ˈˌːˑ0-9\s\-_,.;:!?̀-ͯʰ-˿͜-͢]")


def _strip_marks(ipa: str) -> str:
    return _STRIP.sub("", ipa.lower())


# Ports of Štěpánková & Rosa 2025 helper/IPA_syllabator.py.
_VOCALS_RE = r"[aeiouyæáéíóúýāɑɔəɛɪʊː]"
_CONS_RE = r"[bcdfghjkmnpqstvwxzðňŋɟɡɣɦʔɲʃʒʤʧθř]"
_GREY = r"[rl]"


def _create_word_mask(word: str) -> str:
    rules = [
        ("vər", "v0r"),
        (r"ə(lɪŋ)", r"0\1"),
        (rf"({_GREY})({_GREY})", r"\g<1>0"),
        (rf"({_CONS_RE})({_CONS_RE})\b", r"\g<1>0"),
        (r"[ao][uʊ][iɪ]", "VCV"),
        (r"[ui][əuɪae]", "VV"),
        ("ɪɔ", "VV"),
        ("ɔa", "VV"),
        (r"([aeouæáéóúāɑɔəɛʊː])([iyíɪ])([^lr]|$)", r"\1j\3"),
        (_VOCALS_RE + r"{2}", "0V"),
        (_VOCALS_RE, "V"),
        (rf"([^V])({_GREY})(0*[^0V{_GREY[1:-1]}]|$)", r"\1V\3"),
        (r"s[pt]", "s0"),
        (rf"([^V0lr]0*)[řlrv]", r"\g<1>0"),
        (rf"([^V0]0*)sk", r"\1s0"),
        (rf"([^V0]0*)ʃt", r"\1ʃ0"),
        (_GREY, "C"),
        (_CONS_RE, "C"),
    ]
    for pat, rep in rules:
        word = re.sub(pat, rep, word)
    return word


def _split_mask(mask: str) -> list[str]:
    rules = [
        (r"(^0*V)(C0*V)", r"\1/\2"),
        (r"(^0*V0*C0*)C", r"\1/C"),
        (r"(C0*V(C0*$)?)", r"\1/"),
        (r"/(C0*)C", r"\1/C"),
        (r"/(0*V)(0*C0*V)", r"/\1/\2"),
        (r"/(0*V0*C0*)C", r"/\1/C"),
        (r"/(C0*)$", r"\1/"),
    ]
    for pat, rep in rules:
        mask = re.sub(pat, rep, mask)
    if mask.endswith("/"):
        mask = mask[:-1]
    return mask.split("/")


def _syllabify_en(text: str) -> list[str]:
    """Per-word IPA via eng_to_ipa, split into syllables by S&R 2025's mask rules."""
    syllables: list[str] = []
    for raw in re.findall(r"[a-zA-Z']+", text):
        ipa = re.sub(r"[ˈ'*]", "", eng_to_ipa.convert(raw.lower(), stress_marks="primary"))
        if not ipa or ipa.endswith("*"):
            continue
        mask = _create_word_mask(ipa)
        idx = 0
        for chunk in _split_mask(mask):
            syl = ipa[idx : idx + len(chunk)]
            syllables.append(syl)
            idx += len(chunk)
    return syllables


def _syllabify_zh(text: str) -> list[str]:
    """Each non-punctuation Chinese character is one syllable; transliterated via pinyin."""
    from pypinyin import Style, lazy_pinyin

    chars = [c for c in text if not _STRIP.match(c) and c.strip()]
    if not chars:
        return []
    # Convert each char to pinyin in roman form, then crude pinyin->IPA-ish map.
    sylls: list[str] = []
    for c in chars:
        py = lazy_pinyin(c, style=Style.NORMAL)
        if not py or not py[0]:
            continue
        sylls.append(_pinyin_to_ipa(py[0]))
    return sylls


_PINYIN_INITIAL_IPA = {
    "zh": "ʈʂ", "ch": "ʈʂʰ", "sh": "ʂ", "r": "ɻ",
    "z": "ts", "c": "tsʰ", "s": "s",
    "j": "tɕ", "q": "tɕʰ", "x": "ɕ",
    "b": "p", "p": "pʰ", "m": "m", "f": "f",
    "d": "t", "t": "tʰ", "n": "n", "l": "l",
    "g": "k", "k": "kʰ", "h": "x",
    "y": "j", "w": "w",
}
_PINYIN_FINAL_IPA = {
    "a": "a", "o": "o", "e": "ɤ", "i": "i", "u": "u", "v": "y", "u:": "y",
    "ai": "aɪ", "ei": "eɪ", "ao": "aʊ", "ou": "oʊ",
    "an": "an", "en": "ən", "ang": "aŋ", "eng": "əŋ", "ong": "ʊŋ",
    "ia": "ja", "ie": "je", "iao": "jaʊ", "iu": "joʊ",
    "ian": "jɛn", "in": "in", "iang": "jaŋ", "ing": "iŋ", "iong": "jʊŋ",
    "ua": "wa", "uo": "wo", "uai": "waɪ", "ui": "weɪ",
    "uan": "wan", "un": "wən", "uang": "waŋ", "ueng": "wəŋ",
    "ue": "ɥe", "ve": "ɥe", "uan": "ɥɛn", "un": "ɥn",
    "er": "ɚ",
}


def _pinyin_to_ipa(py: str) -> str:
    """Crude pinyin -> IPA approximation sufficient for CCVO encoding."""
    s = re.sub(r"[1-5]", "", py.lower().replace("ü", "v"))
    # Longest-initial match first
    for init in sorted(_PINYIN_INITIAL_IPA, key=len, reverse=True):
        if s.startswith(init):
            final = s[len(init):]
            ipa_init = _PINYIN_INITIAL_IPA[init]
            ipa_final = _PINYIN_FINAL_IPA.get(final, final)
            return ipa_init + ipa_final
    # No initial: pure-vowel syllable
    return _PINYIN_FINAL_IPA.get(s, s)


_KANA_IPA = {
    "あ": "a", "い": "i", "う": "ɯ", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "kɯ", "け": "ke", "こ": "ko",
    "が": "ga", "ぎ": "gi", "ぐ": "gɯ", "げ": "ge", "ご": "go",
    "さ": "sa", "し": "ɕi", "す": "sɯ", "せ": "se", "そ": "so",
    "ざ": "za", "じ": "dʑi", "ず": "zɯ", "ぜ": "ze", "ぞ": "zo",
    "た": "ta", "ち": "tɕi", "つ": "tsɯ", "て": "te", "と": "to",
    "だ": "da", "ぢ": "dʑi", "づ": "zɯ", "で": "de", "ど": "do",
    "な": "na", "に": "ni", "ぬ": "nɯ", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "çi", "ふ": "ɸɯ", "へ": "he", "ほ": "ho",
    "ば": "ba", "び": "bi", "ぶ": "bɯ", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pɯ", "ぺ": "pe", "ぽ": "po",
    "ま": "ma", "み": "mi", "む": "mɯ", "め": "me", "も": "mo",
    "や": "ja", "ゆ": "jɯ", "よ": "jo",
    "ら": "ɾa", "り": "ɾi", "る": "ɾɯ", "れ": "ɾe", "ろ": "ɾo",
    "わ": "wa", "を": "o", "ん": "ɴ",
    "ぁ": "a", "ぃ": "i", "ぅ": "ɯ", "ぇ": "e", "ぉ": "o",
    "ゃ": "ja", "ゅ": "jɯ", "ょ": "jo",
    "ー": "ː",
}
_KANA_YOON_PREFIXES = {
    "き": "k", "ぎ": "g", "し": "ɕ", "じ": "dʑ", "ち": "tɕ", "ぢ": "dʑ",
    "に": "n", "ひ": "ç", "び": "b", "ぴ": "p", "み": "m", "り": "ɾ",
}


def _syllabify_ja(text: str) -> list[str]:
    """Each Japanese mora is one syllable; kanji read via pykakasi."""
    import pykakasi

    kana = "".join(item["hira"] for item in pykakasi.kakasi().convert(text))
    mora: list[str] = []
    pending_geminate = False
    i = 0
    while i < len(kana):
        ch = kana[i]
        if ch == "っ":
            pending_geminate = True
            i += 1
            continue
        nxt = kana[i + 1] if i + 1 < len(kana) else ""
        if nxt in {"ゃ", "ゅ", "ょ"} and ch in _KANA_YOON_PREFIXES:
            onset = _KANA_YOON_PREFIXES[ch]
            vowel = _KANA_IPA[nxt][1:]  # strip leading 'j'
            syl = onset + "j" + vowel
            i += 2
        elif ch in _KANA_IPA:
            syl = _KANA_IPA[ch]
            i += 1
        else:
            i += 1
            continue
        if pending_geminate:
            syl = (syl[0] if syl else "") + syl
            pending_geminate = False
        mora.append(syl)
    return mora


_pyphen_es = None


def _syllabify_es(text: str) -> list[str]:
    """Spanish: pyphen orthographic syllabification, each syllable -> IPA via espeak."""
    global _pyphen_es
    if _pyphen_es is None:
        import pyphen
        _pyphen_es = pyphen.Pyphen(lang="es_ES")
    from .phonetics import phonemize_text

    syllables: list[str] = []
    for raw in re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]+", text):
        for syl in _pyphen_es.inserted(raw).split("-"):
            ipa = phonemize_text(syl.lower(), "es")
            if ipa.strip():
                syllables.append(ipa)
    return syllables


def syllabify(text: str, lang: str) -> list[str]:
    """Syllabify a text into IPA syllables for the given language."""
    lang = lang.lower()
    if lang.startswith("en"):
        return _syllabify_en(text)
    if lang in ("zh", "cmn", "zh-cn", "zh-tw", "chinese"):
        return _syllabify_zh(text)
    if lang in ("ja", "jp", "japanese"):
        return _syllabify_ja(text)
    if lang in ("es", "spa", "spanish", "es-es"):
        return _syllabify_es(text)
    raise ValueError(f"CCVO syllabification not yet implemented for language '{lang}'")


def _ccvo_mask(syllables: list[str]) -> str:
    """Štěpánková & Rosa 2025, `consonant_clusters_vowel_openness`."""
    mask = ""
    last_C = 0
    for syl in syllables:
        s = _strip_marks(syl)
        start_C = sum(1 for _ in itertools.takewhile(lambda ch: ch in _CONSONANTS, s))
        mask += "C" if last_C + start_C >= 3 else "N"
        if any(ch in _OPEN for ch in s):
            mask += "OO"
        elif any(ch in _MID for ch in s):
            mask += "VO"
        elif any(ch in _CLOSE for ch in s):
            mask += "VV"
        else:
            mask += "VO"  # syllabic r/l fallback (Czech-style)
        last_C = sum(1 for ch in s[start_C:] if ch in _CONSONANTS)
    mask += "C" if last_C >= 3 else "N"
    return mask


def ccvo_string(text: str, lang: str) -> str:
    """Encode a line into a CCVO label string (S&R 2025 spec)."""
    return _ccvo_mask(syllabify(text, lang))


def ccvo_distance(
    src_lines: list[str],
    tgt_lines: list[str],
    src_lang: str,
    tgt_lang: str,
) -> float:
    """Per-line Levenshtein(ccvo_src, ccvo_tgt) / min(len), averaged across lines."""
    n = min(len(src_lines), len(tgt_lines))
    if n == 0:
        return 0.0
    total = 0.0
    for s, t in zip(src_lines[:n], tgt_lines[:n]):
        m1 = ccvo_string(s, src_lang)
        m2 = ccvo_string(t, tgt_lang)
        denom = max(min(len(m1), len(m2)), 1)
        total += Levenshtein.distance(m1, m2) / denom
    return total / n
