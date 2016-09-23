from urllib.request import urlopen
from lxml import html
import os, errno
import pathlib
from itertools import count


class MangaLoader:
    """
    Class used to load manga from mangapark.me
    if manga matches format: volume - chapter - page
    """
    def __init__(self, manga_name_url, save_path, version="s1"):
        self.__manga_name = manga_name_url
        self.__version = version
        self.__save_path = save_path

    def is_valid(self):
        """Check if manga exist and matches volume - chapter - page format"""
        return self.save_page_image(1, 1, 1)

    def save_all(self):
        volume = 1
        chapter_start = 1
        while True:
            exist, chapter_start = self.save_volume(volume, chapter_start)
            if not exist:
                break
            volume += 1

    def save_volume(self, volume, start=1):
        """
        Save volume
        :param volume: volume id
        :param start: assumed first chapter in volume
        :return: pair (True, assumed first chapter of next volume) if exist / pair(False, 0) otherwise
        """
        status, chap = self.save_volume_regular(volume, start)
        if not status:
            return self.save_volume_broken(volume, start)
        else:
            return status, chap

    def save_volume_broken(self, volume, start):
        """
        Used to load volume with broken chapter numeration
        (one chapter named 000 contains all pages)
        """
        status = self.save_chapter(volume, 0)
        if status:
            return True, self.find_volume_first_chapter(volume+1, start)
        else:
            return False, start

    def find_volume_first_chapter(self, volume, start=0, max_count=1000):
        """
        find next volume first chapter
        :param volume: where to search
        :param start: from which chapter id to search
        :param max_count: - tries before stop (if volume do not exist, for example previous was last)
        :return: first chapter in volume id for regular, same value for broken, None if not exist
        """
        if self.save_page_image(volume, 0, 1):
            return start
        for i in range(start, start + max_count):
            if self.save_page_image(volume, i, 1):
                return i
        return None

    def save_volume_regular(self, volume, start):
        """
        Save volume with normal chapter numeration
        (for example volume 1 contain chap 1-6, so volume 2 contain 7-11)
        """
        chapter = start
        if self.save_chapter(volume, chapter):
            while True:
                chapter += 1
                if not self.save_chapter(volume, chapter):
                    break
            return True, chapter
        else:
            return False, 0

    def save_chapter(self, volume, chapter):
        """
        Save chapter
        return True if chapter exist, False otherwise
        """
        i = (self.save_page_image(volume, chapter, page) for page in count(1))
        if next(i):  # test for first page (and load if exist)
            all(i)  # also if first exist load all other pages from chapter
            return True
        else:
            return False

    def save_page_image(self, volume, chapter, page):
        """
        Load page and save on disk
        :return: success code (bool)
        """
        if self.image_exist(self.page_save_path(volume, chapter, page)):
            return True
        try:
            im = PageImage(self.page_path(volume, chapter, page))
            print("{}/{}/{}".format(volume, chapter, page))
            self.ensure_page_location(volume, chapter)
            im.save(self.page_save_path(volume, chapter, page))
            return True
        except (KeyError, OSError):
            return False

    def ensure_page_location(self, volume, chapter):
        """
        test for dir to save page and create it if not exist
        """
        ensure_dir(self.manga_save_path())
        ensure_dir(self.vol_save_path(volume))
        ensure_dir(self.chap_save_path(volume, chapter))

    def page_path(self, volume, chapter, page):
        return "http://mangapark.me/manga/{name}/{ver}/v{vol}/c{chap}/{page}".format(
            name=self.__manga_name,
            ver=self.__version,
            vol=volume,
            chap=chapter,
            page=page
        )

    @staticmethod
    def image_exist(path_without_ext):
        # page images are only files in chapter dirs
        # assuming this enough to check if any file with given name exist
        dir, name = os.path.split(path_without_ext)
        return list(pathlib.Path(dir).glob(name + '.*'))  # if any exist list not empty and it interpreted as True

    def manga_save_path(self):
        return os.path.join(self.__save_path, self.__manga_name)

    def vol_save_path(self, volume):
        return os.path.join(self.manga_save_path(), "{:03d}".format(volume))

    def chap_save_path(self, volume, chapter):
        return os.path.join(self.vol_save_path(volume), "{:03d}".format(chapter))

    def page_save_path(self, volume, chapter, page):
        return os.path.join(self.chap_save_path(volume, chapter), "{:03d}".format(page))


class MangaLoaderNoVolume(MangaLoader):
    """
    class used to load manga from mangapark.me
    if meets format chapter - page
    """
    def ensure_page_location(self, _, chapter):
        # suppress volume value (so chapter dirs inside manga root)
        ensure_dir(self.manga_save_path())
        ensure_dir(self.chap_save_path(_, chapter))

    def chap_save_path(self, _, chapter):
        # suppress volume value (so chapter dirs inside manga root)
        return os.path.join(self.manga_save_path(), str(chapter))

    def page_path(self, _, chapter, page):
        # suppress volume value so url meet required format
        return "http://mangapark.me/manga/{name}/{ver}/c{chap}/{page}".format(
            name=self.__manga_name,
            ver=self.__version,
            chap=chapter,
            page=page
        )

    def save_all(self):
        self.save_volume(1)


class PageImage:
    """
    class used to find manga image in page and save it
    """
    def __init__(self, url):
        """
        :param url: manga page url (not image url)
        """
        root = html.parse(url).getroot()
        self.__image_path = root.get_element_by_id('img-1').get("src")
        self.__data = urlopen(self.__image_path)

    def save(self, path):
        with open(path + '.' + self.get_img_url_ext(self.__image_path), 'wb') as f:
            f.write(self.__data.read())

    @staticmethod
    def get_img_url_ext(url):
        return url.split('?')[0].split('.')[-1]


def ensure_dir(dir_path):
    """ create dir if not exist """
    try:
        os.makedirs(dir_path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def load_manga(name, path):
    """
    Load manga from mangapark.me
    suppor formats:
        volume - chapter - page
        chapter - page
    :param name: manga name
    :param path: manga path
    """
    loader = MangaLoader(name, path)
    if not loader.is_valid():
        loader = MangaLoaderNoVolume(name, path)
    loader.save_all()


if __name__ == '__main__':
    load_manga('anima', 'D:\\manga')
