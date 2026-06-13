# 독서록 아카이브

이 저장소는 `독서 노트.pdf`에서 추출한 독서 노트를 GitHub Pages에 올리기 쉽게 정리한 정적 웹사이트입니다.

- `index.html`: 전체 책 목록
- `notes/`: 책별 독서록 개별 페이지
- `assets/images/`: PDF에서 추출한 책별 이미지
- `data/reading_notes.json`: 추출한 책 제목, 점수, 한줄평, 본문, 이미지 경로 데이터
- `build_reading_archive.py`: 원본 PDF에서 웹사이트를 다시 만드는 스크립트
- `validate_reading_archive.py`: 이미지 경로, 크기, 공개 URL을 검사하는 검증 스크립트

현재 정리된 글 수: 82
추출한 이미지 수: 231

## 다시 만들기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 build_reading_archive.py "/Users/min/Downloads/독서 노트.pdf"
```

GitHub Pages는 `main` 브랜치의 루트(`/`)를 배포 대상으로 사용합니다.

## 검증하기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 validate_reading_archive.py --public
```
