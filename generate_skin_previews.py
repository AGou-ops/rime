#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鼠须管 (Squirrel) 皮肤配色预览图生成工具
遍历 squirrel.yaml 中的 preset_color_schemes 并渲染对应皮肤的高保真预览图及全景网格总览大图。
"""

import os
import sys
import argparse
import yaml
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 候选词与拼音测试数据（与 mingday_hacker 示例保持一致）
SAMPLE_CANDIDATES = [
    ("1.", "这样子", "[zhe yang zi]"),
    ("2.", "这样",   "[zhe yang]"),
    ("3.", "遮阳",   "[zhe yang]"),
    ("4.", "这",     "[zhe]"),
    ("5.", "着",     "[zhe]"),
    ("6.", "者",     "[zhe]"),
    ("7.", "折",     "[zhe]"),
    ("8.", "哲",     "[zhe]"),
]

def get_best_font():
    """获取系统最适合的中英文字体路径"""
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "/System/Library/Fonts/Hiragino Sans GB.ttc"

FONT_PATH = get_best_font()

def parse_rime_color(val, fallback=(0, 0, 0, 255), alpha_scale=1.0):
    """
    解析 Rime / Squirrel 的十六进制颜色值：
    格式为 0x(AA)BBGGRR，如果是 24 位则为 0xBBGGRR。
    返回 RGBA (R, G, B, A) 元组。
    """
    if val is None:
        return fallback

    if isinstance(val, str):
        val = val.strip()
        if val.startswith("0x") or val.startswith("0X"):
            try:
                val = int(val, 16)
            except ValueError:
                return fallback
        elif val.startswith("#"):
            try:
                hex_str = val[1:]
                if len(hex_str) == 6:
                    r = int(hex_str[0:2], 16)
                    g = int(hex_str[2:4], 16)
                    b = int(hex_str[4:6], 16)
                    return (r, g, b, int(255 * alpha_scale))
                elif len(hex_str) == 8:
                    a = int(hex_str[0:2], 16)
                    r = int(hex_str[2:4], 16)
                    g = int(hex_str[4:6], 16)
                    b = int(hex_str[6:8], 16)
                    return (r, g, b, int(a * alpha_scale))
            except ValueError:
                return fallback
        else:
            try:
                val = int(val)
            except ValueError:
                return fallback
    elif isinstance(val, (int, float)):
        val = int(val)
    else:
        return fallback

    # Rime 32位: 0xAABBGGRR, 24位: 0xBBGGRR
    if val > 0xFFFFFF:
        a = (val >> 24) & 0xFF
        b = (val >> 16) & 0xFF
        g = (val >> 8) & 0xFF
        r = val & 0xFF
        return (r, g, b, int(a * alpha_scale))
    else:
        b = (val >> 16) & 0xFF
        g = (val >> 8) & 0xFF
        r = val & 0xFF
        return (r, g, b, int(255 * alpha_scale))

def render_scheme_window(scheme_key, scheme_dict, global_style=None, scale=2):
    """
    渲染单个配色方案的输入法候选窗口（返回带柔和阴影的透明 RGBA 图像）
    """
    if global_style is None:
        global_style = {}
    if not isinstance(scheme_dict, dict):
        scheme_dict = {}

    alpha_val = scheme_dict.get('alpha', global_style.get('alpha', 1.0))
    if not isinstance(alpha_val, (int, float)):
        alpha_val = 1.0

    # 系统原生配色 (native) 特殊回退
    is_native = (scheme_key == 'native')
    default_back = (245, 245, 247, 240) if is_native else (0, 0, 0, 255)
    default_text = (0, 0, 0, 255) if is_native else (220, 220, 220, 255)
    default_hi_bg = (0, 122, 255, 255) if is_native else (45, 13, 255, 255)
    default_hi_txt = (255, 255, 255, 255)

    back_color = parse_rime_color(scheme_dict.get('back_color'), default_back, alpha_val)
    border_color = parse_rime_color(scheme_dict.get('border_color'), back_color, alpha_val)
    
    cand_text_color = parse_rime_color(
        scheme_dict.get('candidate_text_color', scheme_dict.get('text_color')),
        default_text, alpha_val
    )
    label_color = parse_rime_color(
        scheme_dict.get('label_color', scheme_dict.get('candidate_text_color', scheme_dict.get('text_color'))),
        cand_text_color, alpha_val
    )
    comment_color = parse_rime_color(
        scheme_dict.get('comment_text_color', scheme_dict.get('candidate_text_color', scheme_dict.get('text_color'))),
        cand_text_color, alpha_val
    )
    
    hilited_back = parse_rime_color(
        scheme_dict.get('hilited_candidate_back_color', scheme_dict.get('hilited_back_color')),
        default_hi_bg, alpha_val
    )
    hilited_text = parse_rime_color(
        scheme_dict.get('hilited_candidate_text_color', scheme_dict.get('hilited_text_color')),
        default_hi_txt, alpha_val
    )
    hilited_label = parse_rime_color(
        scheme_dict.get('hilited_candidate_label_color'),
        hilited_text, alpha_val
    )
    hilited_comment = parse_rime_color(
        scheme_dict.get('hilited_comment_text_color'),
        hilited_text, alpha_val
    )

    # 字体与字号计算
    font_point = scheme_dict.get('font_point', global_style.get('font_point', 17))
    if not isinstance(font_point, (int, float)) or font_point <= 0:
        font_point = 17
    
    label_point = scheme_dict.get('label_font_point', global_style.get('label_font_point', font_point * 0.85))
    if not isinstance(label_point, (int, float)) or label_point <= 0:
        label_point = font_point * 0.85

    comment_point = scheme_dict.get('comment_font_point', global_style.get('comment_font_point', font_point * 0.95))
    if not isinstance(comment_point, (int, float)) or comment_point <= 0:
        comment_point = font_point * 0.95

    # 圆角与间距
    corner_radius = scheme_dict.get('corner_radius', global_style.get('corner_radius', 6))
    if not isinstance(corner_radius, (int, float)) or corner_radius < 0:
        corner_radius = 6
    hilited_corner_radius = scheme_dict.get('hilited_corner_radius', global_style.get('hilited_corner_radius', 5))
    if not isinstance(hilited_corner_radius, (int, float)) or hilited_corner_radius < 0:
        hilited_corner_radius = 5

    line_spacing = scheme_dict.get('line_spacing', global_style.get('line_spacing', 4))
    if not isinstance(line_spacing, (int, float)) or line_spacing < 0:
        line_spacing = 4

    font_main = ImageFont.truetype(FONT_PATH, int(font_point * scale))
    font_lbl = ImageFont.truetype(FONT_PATH, int(label_point * scale))
    font_comm = ImageFont.truetype(FONT_PATH, int(comment_point * scale))

    row_height = int((font_point + 8) * scale)
    row_space = int(line_spacing * scale)
    pad_x = int(10 * scale)
    pad_y = int(8 * scale)

    # 测量最宽的一行
    max_row_w = 0
    for lbl, cand, comm in SAMPLE_CANDIDATES:
        lbl_bbox = font_lbl.getbbox(lbl)
        cand_bbox = font_main.getbbox(cand)
        comm_bbox = font_comm.getbbox(comm)
        w_cand = cand_bbox[2] - cand_bbox[0]
        w_comm = comm_bbox[2] - comm_bbox[0]
        total_w = int(22 * scale) + w_cand + int(10 * scale) + w_comm
        if total_w > max_row_w:
            max_row_w = total_w

    win_w = max_row_w + pad_x * 2 + int(8 * scale)
    win_h = pad_y * 2 + len(SAMPLE_CANDIDATES) * row_height + (len(SAMPLE_CANDIDATES) - 1) * row_space

    shadow_margin = int(24 * scale)
    img_w = win_w + shadow_margin * 2
    img_h = win_h + shadow_margin * 2

    canvas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    
    # 绘制半透明软阴影
    shadow_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    s_box = [
        shadow_margin,
        shadow_margin + int(4 * scale),
        shadow_margin + win_w,
        shadow_margin + win_h + int(4 * scale)
    ]
    s_draw.rounded_rectangle(s_box, radius=int(corner_radius * scale), fill=(0, 0, 0, 90))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=int(8 * scale)))
    canvas = Image.alpha_composite(canvas, shadow_img)

    # 绘制窗口主体
    win_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    w_draw = ImageDraw.Draw(win_img)
    win_box = [
        shadow_margin,
        shadow_margin,
        shadow_margin + win_w,
        shadow_margin + win_h
    ]
    w_draw.rounded_rectangle(
        win_box,
        radius=int(corner_radius * scale),
        fill=back_color,
        outline=border_color if border_color != back_color else None,
        width=max(1, int(1 * scale))
    )

    # 绘制候选词列表
    cur_y = win_box[1] + pad_y
    for i, (lbl, cand, comm) in enumerate(SAMPLE_CANDIDATES):
        row_top = cur_y
        row_bottom = cur_y + row_height
        
        if i == 0:
            hi_box = [
                win_box[0] + int(3 * scale),
                row_top,
                win_box[2] - int(3 * scale),
                row_bottom
            ]
            w_draw.rounded_rectangle(
                hi_box,
                radius=int(hilited_corner_radius * scale),
                fill=hilited_back
            )
            c_lbl, c_cand, c_comm = hilited_label, hilited_text, hilited_comment
        else:
            c_lbl, c_cand, c_comm = label_color, cand_text_color, comment_color

        text_y = row_top + int(2 * scale)
        lbl_x = win_box[0] + pad_x
        w_draw.text((lbl_x, text_y), lbl, font=font_lbl, fill=c_lbl)

        cand_x = lbl_x + int(20 * scale)
        w_draw.text((cand_x, text_y), cand, font=font_main, fill=c_cand)

        cand_bbox = font_main.getbbox(cand)
        cand_w = cand_bbox[2] - cand_bbox[0]
        comm_x = cand_x + cand_w + int(10 * scale)
        w_draw.text((comm_x, text_y), comm, font=font_comm, fill=c_comm)

        cur_y += row_height + row_space

    canvas = Image.alpha_composite(canvas, win_img)
    return canvas

def generate_all_previews(yaml_path="squirrel.yaml", output_dir="skin_previews", composite_filename="squirrel_skins_all_preview.png"):
    """
    遍历 squirrel.yaml 中所有皮肤，生成各单独图及合并总览大图
    """
    if not os.path.exists(yaml_path):
        print(f"错误: 找不到配置文件 {yaml_path}")
        return

    os.makedirs(output_dir, exist_ok=True)

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    global_style = config.get("style", {})
    schemes = config.get("preset_color_schemes", {})

    print(f"解析到 {len(schemes)} 套皮肤配色方案。")

    rendered_items = []
    scale = 2

    font_title = ImageFont.truetype(FONT_PATH, int(15 * scale))
    font_sub = ImageFont.truetype(FONT_PATH, int(12 * scale))
    font_header_big = ImageFont.truetype(FONT_PATH, int(28 * scale))
    font_header_sub = ImageFont.truetype(FONT_PATH, int(14 * scale))

    for key, scheme in schemes.items():
        if not isinstance(scheme, dict):
            scheme = {}
        name = scheme.get("name", key)
        author = scheme.get("author", "")

        win_img = render_scheme_window(key, scheme, global_style, scale=scale)
        
        # 保存独立皮肤图
        single_path = os.path.join(output_dir, f"{key}.png")
        win_img.save(single_path)
        print(f"  -> 生成独立预览图: {single_path} ({name})")

        rendered_items.append({
            "key": key,
            "name": name,
            "author": author,
            "img": win_img
        })

    # 5 列 × 7 行网格拼接
    cols = 5
    rows = (len(rendered_items) + cols - 1) // cols

    card_w = int(280 * scale)
    card_h = int(320 * scale)
    gap_x = int(24 * scale)
    gap_y = int(24 * scale)
    margin_x = int(40 * scale)
    margin_top = int(110 * scale)
    margin_bottom = int(40 * scale)

    total_w = margin_x * 2 + cols * card_w + (cols - 1) * gap_x
    total_h = margin_top + rows * card_h + (rows - 1) * gap_y + margin_bottom

    bg_color = (24, 24, 28, 255)
    card_bg = (34, 34, 40, 255)
    card_border = (50, 50, 60, 255)

    comp_img = Image.new("RGBA", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(comp_img)

    # 大图顶部标题栏
    title_text = "鼠须管 (Squirrel) 预设皮肤配色方案全览"
    draw.text((margin_x, int(28 * scale)), title_text, font=font_header_big, fill=(255, 255, 255, 255))
    
    sub_text = f"共 {len(rendered_items)} 套配色方案 · 配置源：squirrel.yaml · 格式参考当前 mingday_hacker 样式"
    draw.text((margin_x, int(68 * scale)), sub_text, font=font_header_sub, fill=(160, 165, 180, 255))

    # 绘制各卡片
    for idx, item in enumerate(rendered_items):
        r = idx // cols
        c = idx % cols
        card_x = margin_x + c * (card_w + gap_x)
        card_y = margin_top + r * (card_h + gap_y)

        # 卡片底框
        card_box = [card_x, card_y, card_x + card_w, card_y + card_h]
        draw.rounded_rectangle(card_box, radius=int(10 * scale), fill=card_bg, outline=card_border, width=max(1, int(1 * scale)))

        # 方案标识与名称
        draw.text((card_x + int(14 * scale), card_y + int(12 * scale)), item["key"], font=font_title, fill=(100, 200, 255, 255))
        
        name_str = str(item["name"])
        if len(name_str) > 20:
            name_str = name_str[:19] + "..."
        draw.text((card_x + int(14 * scale), card_y + int(32 * scale)), name_str, font=font_sub, fill=(210, 215, 225, 255))

        # 居中放置候选窗口
        w_img = item["img"]
        max_inner_w = card_w - int(20 * scale)
        max_inner_h = card_h - int(60 * scale)
        scale_ratio = min(1.0, max_inner_w / w_img.width, max_inner_h / w_img.height)
        
        if scale_ratio < 1.0:
            target_w = int(w_img.width * scale_ratio)
            target_h = int(w_img.height * scale_ratio)
            display_win = w_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        else:
            display_win = w_img

        win_x = card_x + (card_w - display_win.width) // 2
        win_y = card_y + int(56 * scale) + (max_inner_h - display_win.height) // 2

        comp_img.alpha_composite(display_win, (win_x, win_y))

    comp_img.save(composite_filename)
    print(f"\n全景总览大图生成成功: {composite_filename}")
    print(f"图像总分辨率: {total_w} x {total_h}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="鼠须管 (Squirrel) 皮肤配色预览图生成工具")
    parser.add_argument("--yaml", default="squirrel.yaml", help="squirrel.yaml 配置文件路径")
    parser.add_argument("--output-dir", default="skin_previews", help="单张预览图输出目录")
    parser.add_argument("--composite", default="squirrel_skins_all_preview.png", help="全览大图输出文件名")
    args = parser.parse_args()

    generate_all_previews(yaml_path=args.yaml, output_dir=args.output_dir, composite_filename=args.composite)
