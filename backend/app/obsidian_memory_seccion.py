
import re
import unicodedata
from pathlib import Path


class ObsidianMemory:
    """Recupera secciones Markdown relevantes de la memoria de BAKI."""

    STOPWORDS = {
        "cual", "cuales", "que", "como", "cuando", "donde",
        "quien", "por", "para", "con", "sin", "del", "las",
        "los", "una", "uno", "unos", "unas", "mi", "mis",
        "tu", "tus", "el", "la", "de", "en", "y", "o",
        "es", "son", "fue", "ser", "estar", "tengo",
        "tiene", "hay", "me", "te", "se", "lo", "su",
        "sus", "un"
    }

    HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    MIN_COVERAGE = 0.50
    MAX_RESULTS = 3
    MAX_CHARS = 3000

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path).resolve()

        if not self.vault_path.is_dir():
            raise FileNotFoundError(
                f"No se encuentra la bóveda: {self.vault_path}"
            )

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.casefold())
        return "".join(
            char for char in text
            if not unicodedata.combining(char)
        )

    def _terms(self, text: str) -> set[str]:
        words = re.findall(r"\w+", self._normalize(text))

        return {
            word[:-1] if word.endswith("s") and len(word) > 4 else word
            for word in words
            if len(word) > 2 and word not in self.STOPWORDS
        }

    def list_documents(self) -> list[str]:
        return [
            str(path.relative_to(self.vault_path))
            for path in self.vault_path.rglob("*.md")
            if path.is_file()
            and ".obsidian" not in path.relative_to(self.vault_path).parts
        ]

    def _sections(self, path: Path) -> list[dict]:
        """Divide documentos en secciones y conserva su jerarquía."""

        rel = str(path.relative_to(self.vault_path))
        sections = []
        stack = []
        lines = []
        in_code = False

        def flush():
            content = "\n".join(lines).strip()

            if content:
                sections.append({
                    "index": len(sections),
                    "document": rel,
                    "heading": " > ".join(
                        [path.stem] + [title for _, title in stack]
                    ),
                    "level": stack[-1][0] if stack else 0,
                    "content": content,
                })

            lines.clear()

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code

            match = None if in_code else self.HEADING.match(line)

            if match:
                flush()

                level = len(match.group(1))

                while stack and stack[-1][0] >= level:
                    stack.pop()

                stack.append((level, match.group(2)))

            lines.append(line)

        flush()
        return sections

    def _score(self, query: str, section: dict, terms: set[str]):
        """Prioriza expresiones completas y encabezados específicos."""

        heading = self._normalize(section["heading"])
        content = self._normalize(section["content"])
        normalized_query = self._normalize(query).strip()

        heading_terms = self._terms(section["heading"])
        content_terms = self._terms(section["content"])

        matched_heading = terms & heading_terms
        matched_content = terms & content_terms
        matched = matched_heading | matched_content

        coverage = len(matched) / len(terms)

        if coverage < self.MIN_COVERAGE:
            return None

        heading_coverage = len(matched_heading) / len(terms)

        score = (
            coverage * 0.50
            + heading_coverage * 0.35
        )

        # Coincidencia de expresión completa.
        exact_heading = bool(
            normalized_query and normalized_query in heading
        )
        exact_content = bool(
            normalized_query and normalized_query in content
        )

        if exact_heading:
            score += 0.20
        elif exact_content:
            score += 0.10

        # Penalizar coincidencias parciales cuando hay varios términos.
        if len(terms) > 1 and coverage < 1:
            score -= 0.15

        return (
            score,
            coverage,
            len(matched_heading),
            section["level"],
        )

    def search(
        self,
        query: str,
        max_results: int = MAX_RESULTS,
        max_chars: int = MAX_CHARS
    ) -> list[dict]:

        terms = self._terms(query)

        if not terms:
            return []

        candidates = []

        for path in self.vault_path.rglob("*.md"):
            if (
                not path.is_file()
                or ".obsidian" in path.relative_to(self.vault_path).parts
            ):
                continue

            try:
                sections = self._sections(path)
            except (OSError, UnicodeError):
                continue

            for section in sections:
                ranking = self._score(query, section, terms)

                if ranking is None:
                    continue

                score, coverage, title_hits, level = ranking

                candidates.append({
                    "score": score,
                    "coverage": coverage,
                    "title_hits": title_hits,
                    "level": level,
                    "section": section,
                })

        candidates.sort(
            key=lambda item: (
                item["score"],
                item["coverage"],
                item["title_hits"],
                item["level"],
            ),
            reverse=True
        )

        results = []
        seen = set()
        total_chars = 0

        for candidate in candidates:
            if len(results) >= max_results:
                break

            section = candidate["section"]
            key = (section["document"], section["index"])

            if key in seen:
                continue

            remaining = max_chars - total_chars

            if remaining <= 0:
                break

            content = section["content"]

            if len(content) > remaining:
                if results:
                    break
                content = content[:remaining]

            results.append({
                "document": (
                    f"{section['document']} | {section['heading']}"
                ),
                "content": content,
            })

            total_chars += len(content)
            seen.add(key)

        return results
