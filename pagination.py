from pyrogram.types import Message

from plugins import MangaChapter
from typing import List


class Pagination:
    pagination_id: int = 0
    
    def __init__(self):
        self.id = self.pagination_id
        Pagination.pagination_id += 1
        self.page = 1
        self.count = 20
        self.message: Message = None
        self.chapters: List[MangaChapter] = None

    def get_chapters(self):
        return self.chapters[(self.page - 1) * self.count:self.page * 20]

    @property
    def is_first_page(self):
        return self.page == 1

    @property
    def is_last_page(self):
        return self.page == (len(self.chapters) + self.count - 1) // self.count
