# 🚗 Diecast Catalog

Live catalog at: `https://YOUR-USERNAME.github.io/diecast-catalog`

---

## 📅 Daily Update (takes 2 minutes)

1. Go to your repository on **github.com**
2. Click on **`products.csv`**
3. Click the **pencil ✏️ icon** (Edit) — or drag & drop a new file
4. If drag & drop: click **"Upload files"** → drop your new CSV → **Commit changes**
5. GitHub will automatically rebuild the catalog in ~60 seconds
6. Refresh your iPhone link — done! ✅

---

## 📁 File Structure

```
diecast-catalog/
├── products.csv          ← Replace this daily
├── build.py              ← Auto-runs on GitHub, don't touch
├── index.html            ← Auto-generated, don't touch
└── .github/
    └── workflows/
        └── build.yml     ← GitHub Actions config, don't touch
```

---

## ⚙️ First-Time Setup

1. Create a free account at [github.com](https://github.com)
2. Create a new **public** repository named `diecast-catalog`
3. Upload all files from this folder
4. Go to **Settings → Pages → Branch: main → Save**
5. Your link will be live at `https://YOUR-USERNAME.github.io/diecast-catalog`
