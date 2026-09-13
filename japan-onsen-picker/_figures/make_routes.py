"""도시별 3박 4일 동선을 일본 지도 위에 그린다.

좌표는 실제 위경도라 거리감이 그대로 보인다. 수치나 동선이 바뀌면 이 스크립트를 다시 돌린다.

배경 지도는 용량이 커서 레포에 두지 않는다. 없으면 먼저 받는다:
    curl -sL https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson \
         -o _figures/japan.geojson
"""

import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

FONT = "Pretendard"
plt.rcParams["font.family"] = FONT
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..")

SEA = "#DCE7E5"
LAND = "#F4F1EC"
LAND_EDGE = "#CBD4D2"
INK = "#17211F"
SOFT = "#5B6B68"

# 지점: (이름, 위도, 경도, 종류)  종류 — air 공항 · stay 숙박 · spot 관광
ROUTES = {
    "sendai": {
        "title": "센다이 · 아키우온천",
        "accent": "#B5632F",
        "prefs": ["Miyagi Ken", "Yamagata Ken", "Iwate Ken", "Fukushima Ken"],
        "points": [
            ("센다이공항", 38.1397, 140.9170, "air"),
            ("센다이 시내", 38.2601, 140.8825, "stay"),
            ("마츠시마", 38.3697, 141.0603, "spot"),
            ("아키우온천", 38.2361, 140.7183, "stay"),
        ],
        "legs": [(0, 1, "공항철도 25분"), (1, 2, "JR 40분"), (2, 3, "버스 50분")],
        "stays": {1: "1·2박", 3: "3박"},
        "note": "시내 2박 → 아키우온천 1박. 모든 구간이 한 시간 안이다.",
    },
    "hakodate": {
        "title": "하코다테 · 유노카와온천",
        "accent": "#2F6B8F",
        "prefs": ["Hokkai Do"],
        "zoom": (41.728, 41.822, 140.672, 140.862),
        "points": [
            ("하코다테공항", 41.7700, 140.8222, "air", "down"),
            ("유노카와온천", 41.7772, 140.7897, "stay", "up"),
            ("아침시장·역", 41.7736, 140.7263, "spot", "up"),
            ("모토마치·하코다테산", 41.7600, 140.7070, "spot", "down"),
        ],
        "legs": [(0, 1, "버스 6분"), (1, 2, "전차 25분"), (2, 3, "도보·전차 10분")],
        "stays": {1: "1·2·3박"},
        "note": "온천에 3박. 짐을 한 번만 옮기고 매일 같은 방으로 돌아온다.",
    },
    "kanazawa": {
        "title": "가나자와 · 유와쿠온천",
        "accent": "#9E3B4A",
        "prefs": ["Ishikawa Ken", "Toyama Ken", "Fukui Ken", "Gifu Ken"],
        "points": [
            ("고마쓰공항", 36.3946, 136.4075, "air"),
            ("가나자와 시내\n겐로쿠엔·차야가이", 36.5700, 136.6550, "stay"),
            ("유와쿠온천", 36.4783, 136.7500, "stay"),
        ],
        "legs": [(0, 1, "리무진 40분"), (1, 2, "차 25분 (송영)")],
        "stays": {1: "1·2박", 2: "3박"},
        "note": "시내 2박 → 유와쿠온천 1박. 여관 무료 송영이 있다.",
    },
    "aomori": {
        "title": "아오모리 · 아사무시온천",
        "accent": "#3F6B4A",
        "prefs": ["Aomori Ken", "Akita Ken", "Iwate Ken"],
        "points": [
            ("아오모리공항", 40.7347, 140.6907, "air"),
            ("아오모리 시내", 40.8280, 140.7350, "stay"),
            ("아사무시온천", 40.8930, 140.8600, "stay"),
        ],
        "legs": [(0, 1, "버스 35분"), (1, 2, "철도 20분")],
        "stays": {1: "1박", 2: "2·3박"},
        "note": "시내에서 네부타 박물관 → 아사무시온천으로 들어간다.",
    },
    "yonago": {
        "title": "요나고 · 마쓰에 · 가이케온천",
        "accent": "#6B5B8F",
        "prefs": ["Tottori Ken", "Shimane Ken"],
        "zoom": (35.33, 35.61, 132.90, 133.45),
        "points": [
            ("요나고공항", 35.4923, 133.2364, "air"),
            ("가이케온천", 35.4480, 133.2700, "stay", "right"),
            ("아다치미술관", 35.4110, 133.1990, "spot", "down"),
            ("마쓰에성", 35.4750, 133.0506, "spot", "up"),
            ("타마쓰쿠리온천", 35.4253, 132.9847, "stay", "down"),
        ],
        "legs": [(0, 1, "택시 20분"), (1, 2, "JR+셔틀 30분"), (2, 3, "JR 30분"),
                 (3, 4, "JR 10분")],
        "stays": {1: "1·2박", 4: "3박"},
        "note": "가이케온천 2박 + 타마쓰쿠리 1박. 대게의 본고장이다.",
    },
}

# 종류는 글리프 대신 마커 모양으로 구분한다 (Pretendard에 ✈·♨ 글리프가 없다)
MARK = {
    "air":  ("s", 300),   # 공항 — 사각
    "stay": ("o", 300),   # 숙박 — 원
    "spot": ("o", 230),   # 관광 — 작은 원
}


def load_prefs(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for feat in data["features"]:
        name = feat["properties"]["nam"]
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        out[name] = [ring[0] for ring in polys]
    return out


def draw(key, cfg, prefs):
    pts = cfg["points"]
    lats = [p[1] for p in pts]
    lons = [p[2] for p in pts]

    if "zoom" in cfg:
        y0, y1, x0, x1 = cfg["zoom"]
    else:
        pad_y = max((max(lats) - min(lats)) * 0.55, 0.10)
        pad_x = max((max(lons) - min(lons)) * 0.45, 0.13)
        y0, y1 = min(lats) - pad_y, max(lats) + pad_y
        x0, x1 = min(lons) - pad_x, max(lons) + pad_x

    # 경도 1도는 위도에 따라 짧아진다 — 화면 비율을 실제 거리에 맞춘다
    kx = math.cos(math.radians((y0 + y1) / 2))
    w, h = (x1 - x0) * kx, (y1 - y0)
    fig_w = 7.2
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * h / w))
    fig.patch.set_facecolor("white")
    ax.set_facecolor(SEA)

    for name in cfg["prefs"]:
        for ring in prefs.get(name, []):
            ax.fill(*zip(*ring), facecolor=LAND, edgecolor=LAND_EDGE, linewidth=0.7, zorder=1)

    accent = cfg["accent"]
    for a, b, label in cfg["legs"]:
        (_, ya, xa), (_, yb, xb) = pts[a][:3], pts[b][:3]
        ax.add_patch(FancyArrowPatch(
            (xa, ya), (xb, yb), arrowstyle="-|>", mutation_scale=15,
            linewidth=2.0, color=accent, alpha=.85, zorder=4,
            connectionstyle="arc3,rad=0.14", shrinkA=13, shrinkB=15))
        # arc3 곡선의 제어점 → 2차 베지어 t=0.5 지점이 실제 곡선 중앙이다
        rad = 0.14
        cx = (xa + xb) / 2 + rad * (yb - ya)
        cy = (ya + yb) / 2 - rad * (xb - xa) * kx * kx
        mx, my = (xa + 2 * cx + xb) / 4, (ya + 2 * cy + yb) / 4
        ax.text(mx, my, label, fontsize=9.5, color=accent, weight="bold",
                ha="center", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.30", fc="white", ec=accent, lw=0.8, alpha=.97))

    for i, p in enumerate(pts):
        name, lat, lon = p[0], p[1], p[2]
        kind = p[3] if len(p) > 3 else "spot"
        marker, size = MARK[kind]
        ax.scatter([lon], [lat], s=size, marker=marker, color="white",
                   edgecolors=accent, linewidths=2.3, zorder=7)
        ax.text(lon, lat, str(i + 1), fontsize=9.5, weight="bold", color=accent,
                ha="center", va="center", zorder=8)
        # 라벨은 그 지점에 붙은 화살표들의 반대편에 둔다 — 안 그러면 화살표가 글자를 관통한다
        forced = p[4] if len(p) > 4 else None
        vx = vy = 0.0
        for a, b, _ in cfg["legs"]:
            other = b if a == i else a if b == i else None
            if other is None:
                continue
            vx += (pts[other][2] - lon) * kx
            vy += pts[other][1] - lat
        DIRS = {"up": (0.0, 1.0), "down": (0.0, -1.0),
                "left": (-1.0, 0.0), "right": (1.0, 0.0)}
        if forced:
            ux, uy = DIRS[forced]
        else:
            mag = math.hypot(vx, vy)
            ux, uy = (0.0, -1.0) if mag < 1e-9 else (-vx / mag, -vy / mag)
        dy = (y1 - y0) * (0.082 if "\n" in name else 0.068)
        dx = dy / kx
        ax.text(lon + ux * dx, lat + uy * dy, name,
                fontsize=10.5, color=INK, weight="bold" if kind != "spot" else "normal",
                ha="center", va="center", zorder=8,
                bbox=dict(boxstyle="round,pad=0.30", fc="white", ec="none", alpha=.92))
        nights = cfg.get("stays", {}).get(i)
        if nights:
            lines = name.count("\n") + 1
            # 배지는 라벨과 같은 x에 두고 수직으로 한 줄만 옮긴다.
            # 가로로 밀면 라벨 글자를 덮고, 노드 쪽으로 당기면 번호를 덮는다.
            step = (y1 - y0) * 0.045 * lines
            vdir = 1.0 if uy > 0.3 else -1.0
            ax.text(lon + ux * dx, lat + uy * dy + vdir * step,
                    nights, fontsize=9, color="white", weight="bold",
                    ha="center", va="center", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.32", fc=accent, ec="none"))

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / kx)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(LAND_EDGE)

    ax.set_title(cfg["title"], fontsize=14.5, weight="bold", color=INK, pad=11, loc="left")
    fig.text(0.011, 0.017, cfg["note"], fontsize=10, color=SOFT)

    # 축척 — 지도에서 거리를 가늠할 수 있게
    km_deg = 111.32 * kx
    bar_km = 10 if (x1 - x0) * km_deg < 90 else 20
    bx, by = x0 + (x1 - x0) * 0.055, y0 + (y1 - y0) * 0.055
    ax.plot([bx, bx + bar_km / km_deg], [by, by], color=SOFT, lw=2.4, zorder=9)
    ax.text(bx + bar_km / km_deg / 2, by + (y1 - y0) * 0.016, f"{bar_km}km",
            fontsize=8.5, color=SOFT, ha="center", zorder=9)

    ax.scatter([], [], s=90, marker="s", color="white", edgecolors=accent,
               linewidths=2.0, label="공항")
    ax.scatter([], [], s=90, marker="o", color="white", edgecolors=accent,
               linewidths=2.0, label="묵는 곳")
    ax.scatter([], [], s=55, marker="o", color="white", edgecolors=accent,
               linewidths=1.6, label="들르는 곳")
    leg = ax.legend(loc="upper right", fontsize=9, frameon=True, framealpha=.95,
                    facecolor="white", edgecolor=LAND_EDGE, borderpad=.6, labelspacing=.55)
    leg.set_zorder(10)

    path = os.path.join(OUT, f"route-{key}.png")
    fig.savefig(path, dpi=155, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def main():
    prefs = load_prefs(os.path.join(HERE, "japan.geojson"))
    for key, cfg in ROUTES.items():
        print("생성:", draw(key, cfg, prefs))


if __name__ == "__main__":
    main()
