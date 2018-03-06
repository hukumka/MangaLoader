from os import path
import os

from bs4 import BeautifulSoup
import requests

from MangaLoader import ensure_dir
from MangaLoader import PageImage
from MangaLoader import find_manga


class MangaPageScrapper:
    BASE_URL = "https://mangapark.me"

    def __init__(self, name, version):
        """
        initialize main page scrapper
            name: Manga url name
            version: Desired version. Sometimes some versions could be skipped
            (versions 1, 2, 3 and 5 exists, but not 4)
        """
        self.__name = name
        self.__version = version

        r = requests.get(self.BASE_URL + "/manga/" + self.__name)
        if r.status_code == 200:
            self.__page_html = r.text
            self.__soup = BeautifulSoup(self.__page_html, 'html.parser')
            self.__contents_root = self.__soup.find(id="list")
            version_root = self.__contents_root.find_all(id="stream_"+str(version))
            if len(version_root) != 1:
                raise MangaPageScrapperError("no such version!")
            self.__version_root = version_root[0]

            self._volumes = self.__scrap_volume_list()
        else:
            r.raise_for_status()

    def __scrap_volume_list(self):
        volumes = self.__version_root.find_all(class_=lambda x: x is not None and x.startswith("volume"))
        return [{"root": x, "chapters": self.__scrap_volume_chapters(x)} for x in volumes][::-1]

    def __scrap_volume_chapters(self, volume_root):
        chapters = volume_root.find("ul", class_="chapter")
        chapters = chapters.find_all("li")
        return [{"root": x, "pages": self.__scrap_chapter_pages(x)} for x in chapters][::-1]

    def __scrap_chapter_pages(self, chapter_root):
        em = chapter_root.find("em")
        page_count = int(em.contents[-1].strip()[3:])
        base_url = em.find("a", text="all")["href"]
        return ["{}{}/{}".format(self.BASE_URL, base_url, i+1) for i in range(page_count)]

    def info(self):
        vol_count = len(self._volumes)
        chap_count = 0
        page_count = 0
        for v in self._volumes:
            chap_count += len(v["chapters"])
            for c in v["chapters"]:
                page_count += len(c["pages"])
        print("volume count = {}; chapter count = {}; page count = {}".format(vol_count, chap_count, page_count))

    def iter_pages(self, volume_filter: lambda _: True):
        for (vol_id, vol) in enumerate(self._volumes):
            if volume_filter(vol):
                for (chap_id, chap) in enumerate(vol["chapters"]):
                    for (page_id, page) in enumerate(chap["pages"]):
                        yield {
                            "volume_id": vol_id,
                            "chapter_id": chap_id,
                            "page_id": page_id,
                            "page_url": page
                        }

    @staticmethod
    def is_volume_null(volume):
        volume_root = volume["root"]
        return len(volume_root.h4.contents) == 3


class MangaPageScrapperError(Exception):
    pass


class MangaLoader:
    def __init__(self, name,  version=1, volume_policy=MangaPageScrapper.is_volume_null):
        self.__volume_policy = volume_policy
        self.__scrapper = MangaPageScrapper(name, version)

    def load(self, path):
        for p in self.__scrapper.iter_pages(self.__volume_policy):
            image_dir = "{}/{:03}/{:03}/".format(path, p["volume_id"], p["chapter_id"])
            image_path = "{}{:03}".format(image_dir, p["page_id"])
            ensure_dir(image_dir)
            if self.need_to_load(image_path):
                print("downloading: " + p["page_url"])
                PageImage(p["page_url"]).save(image_path)
            else:
                print("skipping: " + p["page_url"])

    def need_to_load(self, save_path):
        dir, page_id = path.split(save_path)
        for file in os.listdir(dir):
            if file.startswith(page_id):
                return False
        return True

    def info(self):
        self.__scrapper.info()

    @staticmethod
    def find_and_load(name, path, version=1, volume_policy=MangaPageScrapper.is_volume_null):
        name = find_manga(name)
        print(name)
        loader = MangaLoader(name, version, volume_policy)
        loader.info()
        loader.load(path)


if __name__ == "__main__":
    MangaLoader.find_and_load("one piece", "D:/manga/one_piece", volume_policy=lambda _: True)
