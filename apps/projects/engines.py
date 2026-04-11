import re

from .models import ProjectLabel


class ProjectLabelEngineService:
    STOP_WORDS = {
        "a",
        "an",
        "the",
        "of",
        "from",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "and",
        "or",
        "but",
        "with",
        "into",
        "onto",
        "upon",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "via",
        "per",
    }

    def tokenise(text: str):
        return [t for t in re.split(r"[\s\-_/]+", text.strip()) if t]

    def programme_slug(name: str):
        """
        Rules (in priority order):
        1. 'Others' (case-insensitive) → empty string (no prefix).
        2. Single token that is all-uppercase + optional trailing version number
        (e.g. 'XTY2.0', 'CCD') → use as-is, merged.
        3. First token is consecutive uppercase letters followed immediately by a
        version suffix (int or decimal) → merge first token + version, skip
        generic subsequent tokens (e.g. 'XTY 2.0' → 'XTY2.0',
        'XTY Platform 2.0' → 'XTY2.0').
        4. First token is all-uppercase consecutive chars (acronym-like, e.g. 'CCD')
        → use that token; append initials of remaining non-generic, non-version
        tokens only if they add meaning.
        5. General: first letter of each non-generic token, uppercased.
        """
        tokens = ProjectLabelEngineService.tokenise(name)
        if not tokens:
            return ""

        if tokens[0].strip().upper() == "OTHERS" and len(tokens) == 1:
            return ""

        if name.strip().upper() == "OTHERS":
            return ""

        # Identify version tokens: purely numeric or decimal (e.g. '2', '2.0', '3.1')
        def is_version(t: str) -> bool:
            return bool(re.match(r"^\d+(\.\d+)?$", t))

        def is_all_caps_word(t: str) -> bool:
            # All letters are uppercase, no lowercase present, at least 2 chars
            letters = re.sub(r"[^A-Za-z]", "", t)
            return len(letters) >= 2 and letters == letters.upper()

        first = tokens[0]
        first_upper = re.sub(r"[^A-Z0-9]", "", first.upper())

        # Find an adjacent version token (position 1 or merged into first token)
        merged_version = ""
        remaining_start = 1
        if len(tokens) > 1 and is_version(tokens[1]):
            merged_version = tokens[1]
            remaining_start = 2
        else:
            # version number might be embedded: 'XTY2.0' as single token
            m = re.match(r"^([A-Za-z]+)(\d+(?:\.\d+)?)$", first)
            if m:
                first_upper = m.group(1).upper()
                merged_version = m.group(2)
                remaining_start = 1

        if is_all_caps_word(first) or (
            len(re.sub(r"[^A-Za-z]", "", first)) >= 2 and first == first.upper()
        ):
            base = first_upper + merged_version
            # skip generic / version tokens in remainder; take initials of meaningful ones
            extras = [
                t[0].upper()
                for t in tokens[remaining_start:]
                if t.lower() not in ProjectLabelEngineService.STOP_WORDS
                and not is_version(t)
                and re.sub(r"[^A-Za-z]", "", t)
            ]
            # Only append extras if they genuinely add meaning (non-generic words exist)
            if extras and not merged_version:
                base += "".join(extras)
            return base

        # General: initials of all non-generic tokens
        initials = [
            t[0].upper()
            for t in tokens
            if t.lower() not in ProjectLabelEngineService.STOP_WORDS
            and not is_version(t)
            and re.sub(r"[^A-Za-z]", "", t)
        ]
        version_suffix = merged_version if merged_version else ""
        return "".join(initials) + version_suffix

    def project_slug_words(name: str, max_words: int = 4):
        """
        Return a list of meaningful uppercase tokens from the project name.
        - Filters stop words.
        - Prefers domain/noun words over generic ones.
        - Returns between 1 and max_words tokens.
        - If all words are stop words, returns all tokens uppercased.
        """
        tokens = ProjectLabelEngineService.tokenise(name)
        meaningful = [
            re.sub(r"[^A-Z0-9]", "", t.upper())
            for t in tokens
            if t.lower() not in ProjectLabelEngineService.STOP_WORDS
            and re.sub(r"[^A-Za-z0-9]", "", t)
        ]
        if not meaningful:
            meaningful = [re.sub(r"[^A-Z0-9]", "", t.upper()) for t in tokens if t]

        meaningful = [m for m in meaningful if m]
        return meaningful[:max_words]

    def build_candidates(
        programme_name: str | None, project_name: str, max_label: int = 50
    ):
        """
        Return an ordered list of candidate label strings (without collision suffix).
        Patterns tried (shortest meaningful first, then longer):
        P1: PROG_WORD1
        P2: PROG_WORD1_WORD2
        P3: PROG_WORD1WORD2  (merged, no underscore between project words)
        P4: PROG_WORD1_WORD2_WORD3
        P5: PROG_WORD1_WORD2_WORD3_WORD4
        When programme is empty (Others), no prefix.
        """
        prog = (
            ProjectLabelEngineService.programme_slug(programme_name)
            if programme_name
            else ""
        )
        words = ProjectLabelEngineService.project_slug_words(project_name)

        def join_proj(*parts) -> str:
            slug = "_".join(p for p in parts if p)
            return f"{prog}_{slug}" if prog else slug

        def join_proj_merged(*parts) -> str:
            slug = "".join(p for p in parts if p)
            return f"{prog}_{slug}" if prog else slug

        candidates: list[str] = []
        seen: set[str] = set()

        def add(c: str):
            c = c.strip("_")
            if c and c not in seen and len(c) <= max_label:
                seen.add(c)
                candidates.append(c)

        if not words:
            add(prog)
            return candidates

        # P1: single word
        add(join_proj(words[0]))

        if len(words) >= 2:
            # P2: two words underscored
            add(join_proj(words[0], words[1]))
            # P3: two words merged
            add(join_proj_merged(words[0], words[1]))

        if len(words) >= 3:
            add(join_proj(words[0], words[1], words[2]))

        if len(words) >= 4:
            add(join_proj(words[0], words[1], words[2], words[3]))

        return candidates

    def resolve_collision(base: str):
        if not ProjectLabel.objects.filter(label=base).exists():
            return base

        suffix = 2
        while True:
            candidate = f"{base}_{suffix}"
            if not ProjectLabel.objects.filter(label=candidate).exists():
                return candidate
            suffix += 1
