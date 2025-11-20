import sqlite3
import os
import logging
import datetime

LOGGER = logging.getLogger(__name__)

class Memory:
    """
    Long-term memory for the assistant using SQLite.
    Stores user facts and retrieves them by keyword matching.
    """
    def __init__(self, db_path="petro_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            LOGGER.error(f"Memory Init Error: {e}")

    def save_fact(self, text: str):
        """Saves a piece of information."""
        try:
            # Clean up "remember that..." prefixes
            prefixes = ["запам'ятай", "запам'ятай що", "занотуй", "remember"]
            clean_text = text
            for p in prefixes:
                if clean_text.lower().startswith(p):
                    clean_text = clean_text[len(p):].strip()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO facts (text) VALUES (?)", (clean_text,))
            conn.commit()
            conn.close()
            return "Запам'ятав."
        except Exception as e:
            return f"Помилка запису в пам'ять: {e}"

    def search_facts(self, query: str, limit=3) -> str:
        """Finds relevant facts for a query (Simple Keyword Search)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM facts")
            rows = cursor.fetchall()
            conn.close()
            
            # Very basic relevance: count matching words
            query_words = set(query.lower().split())
            results = []
            
            for (fact,) in rows:
                fact_words = set(fact.lower().split())
                # Intersect
                common = query_words.intersection(fact_words)
                if len(common) > 0:
                    results.append((len(common), fact))
            
            # Sort by number of matches
            results.sort(key=lambda x: x[0], reverse=True)
            
            if not results:
                return ""
            
            top_facts = [r[1] for r in results[:limit]]
            return "Знайдені факти в пам'яті:\n" + "\n".join(f"- {f}" for f in top_facts)
            
        except Exception as e:
            LOGGER.error(f"Memory Search Error: {e}")
            return ""

    def get_all_facts(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT text, created_at FROM facts ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except: return []

    def clear_memory(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM facts")
            conn.commit()
            conn.close()
            return "Пам'ять очищено."
        except: return "Помилка."