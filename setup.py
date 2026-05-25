from setuptools import setup, find_packages

setup(
    name="web-scraper-cli",
    version="1.0.0",
    description="轻量网页爬虫 CLI 工具",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="有灵",
    author_email="youling.dev@outlook.com",
    url="https://github.com/youling-dev/web-scraper-cli",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28",
        "beautifulsoup4>=4.12",
        "fake-useragent>=1.4",
        "lxml",
    ],
    entry_points={
        "console_scripts": [
            "wscraper=wscraper.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
