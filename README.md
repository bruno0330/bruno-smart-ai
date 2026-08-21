# Bruno Smart AI Ltd.

一人公司的 AI 工具集合站。入口頁按「處／部」分類，每個部門是 Claude 與使用者一起開發的一項實際工具。

## 結構

```
index.html              入口頁
data/gvm_index_full.json 共用資料庫（遠見雜誌 29,583 篇文章索引）
smart-curation/          智能策展部（遠見線上讀）
ceo-secretary/           CEO秘書部（規劃中）
```

## 開發模式

- 這個 repo 由多個 Claude Code 對話協作完成：一個對話負責整體架構，各部門在各自獨立的對話中開發，最終都整合進這個 repo。
- 部署：GitHub Pages，網址 `https://bruno0330.github.io/bruno-smart-ai/`。
