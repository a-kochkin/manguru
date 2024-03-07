from clients import MangaChapter
from typing import List


class Pagination:
    pagination_id: int = 0
    
    def __init__(self):
        self.id = self.pagination_id
        Pagination.pagination_id += 1
        self.count = 20
        self.chapters: List[MangaChapter] = []

    def get_page_chapters(self, page: int):
        return self.chapters[(page - 1) * self.count:page * 20]

    def get_prev_page(self, page: int):
        if page == 1:
            return None
        return page - 1

    def get_next_page(self, page: int):
        if page == (len(self.chapters) + self.count - 1) // self.count:
            return None
        return page + 1

    def get_prev_chapter(self, target: MangaChapter):
        for i, chapter in enumerate(self.chapters):
            if target == chapter:
                if i == 0:
                    return None
                else:
                    return self.chapters[i - 1]
        return None

    def get_next_chapter(self, target: MangaChapter):
        for i, chapter in enumerate(self.chapters):
            if target == chapter:
                if i == len(self.chapters) - 1:
                    return None
                else:
                    return self.chapters[i + 1]
        return None
