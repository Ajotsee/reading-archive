# 독서록 아카이브

이 폴더는 `독서 노트.pdf`에서 추출한 독서 노트를 깃허브 Pages에 올리기 쉽게 정리한 정적 웹페이지입니다.

- `index.html`: 바로 배포할 수 있는 한 페이지 웹사이트
- `data/reading_notes.json`: 추출한 책 제목, 점수, 한줄평, 본문 데이터
- `build_reading_archive.py`: 원본 PDF에서 웹페이지를 다시 만드는 스크립트

현재 정리된 글 수: 82

## 다시 만들기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 build_reading_archive.py "/Users/min/Downloads/독서 노트.pdf"
```

깃허브에 올릴 때는 이 폴더 전체를 저장소에 넣고 Pages에서 루트 또는 `/docs` 대신 이 폴더를 기준으로 배포하면 됩니다.
