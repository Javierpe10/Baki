
import re
import unicodedata
from pathlib import Path


class ObsidianMemory:
    """Consulta selectivamente la memoria documental de BAKI."""

    STOPWORDS = {
        "cual", "cuales", "que", "como", "cuando", "donde",
        "quien", "por", "para", "con", "sin", "del", "las",
        "los", "una", "uno", "unos", "unas", "mi", "mis",
        "tu", "tus", "el", "la", "de", "en", "y", "o",
        "es", "son", "fue", "ser", "estar", "tengo",
        "tiene", "hay", "me", "te", "se", "lo", "su",
        "sus", "un"
    }

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

    def search(
        self,
        query: str,
        max_results: int = 3,
        max_chars: int = 3000
    ) -> list[dict]:
        """Recupera fragmentos relevantes, no documentos completos."""

        terms = self._terms(query)

        if not terms:
            return []

        matches = []

        for path in self.vault_path.rglob("*.md"):
            if (
                not path.is_file()
                or ".obsidian" in path.relative_to(self.vault_path).parts
            ):
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue

            paragraphs = re.split(r"\n\s*\n", content)

            for paragraph in paragraphs:
                paragraph = paragraph.strip()

                if not paragraph:
                    continue

                normalized = self._normalize(paragraph)
                paragraph_terms = self._terms(paragraph)
                common_terms = terms.intersection(paragraph_terms)

                if not common_terms:
                    continue

                score = len(common_terms) / len(terms)

                if score >= 0.2:
                    matches.append({
                        "document": str(
                            path.relative_to(self.vault_path)
                        ),
                        "content": paragraph,
                        "score": score
                    })

        matches.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        results = []
        total_chars = 0

        for match in matches:
            if len(results) >= max_results:
                break

            remaining = max_chars - total_chars

            if remaining <= 0:
                break

            fragment = match["content"][:remaining]

            results.append({
                "document": match["document"],
                "content": fragment
            })

            total_chars += len(fragment)

        return results
