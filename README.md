# 세무판례 분석 시스템 - Cloudflare Pages 배포

## 폴더 구조
```
/
├── index.html               ← 메인 페이지
└── functions/
    └── api/
        ├── search.js        ← 판례 목록 검색 API
        ├── detail.js        ← 판례 상세 조회 API
        └── health.js        ← 상태 확인 API
```

## 배포 방법 (GitHub + Cloudflare Pages)

1. GitHub에 새 저장소 생성
2. 위 파일 전체를 업로드
3. Cloudflare Pages에서 해당 저장소 연결
4. 빌드 설정 없음 (정적 사이트)
5. 배포 완료 후 제공된 URL로 접속

