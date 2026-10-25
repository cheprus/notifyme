# calendar_icon.py
import os
from AppKit import NSImage, NSColor, NSBezierPath, NSMakeRect, NSMakeSize, NSBitmapImageRep, NSGraphicsContext
from Foundation import NSData

def generate_hourglass_icon(color_rgb, path="/tmp/notifyme_icon.png", fill_ratio=1.0, flipped=False, blink=False, size=22):
    """
    Рисует песочные часы с правильной физикой песка.
    size: размер иконки (22 для трея, 1024 для приложения)
    """
    img = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    img.lockFocus()
    
    scale = size / 22.0  # Коэффициент масштабирования от базового размера 22
    
    # Прозрачный фон
    NSColor.clearColor().set()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, size, size))
    
    alpha = 0.3 if blink else 1.0
    
    sand_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
        color_rgb[0], color_rgb[1], color_rgb[2], alpha
    )
    # Делаем стекло чуть более заметным
    glass_color = NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.4 * alpha)
    # Контур делаем всегда контрастным (темно-серым или белым в зависимости от темы)
    # Для универсальности используем полупрозрачный белый + темный
    outline_color = NSColor.colorWithCalibratedWhite_alpha_(0.3, 1.0 * alpha) 
    
    # Координаты (умноженные на scale)
    def S(val): return val * scale
    
    if not flipped:
        top_y_bottom = S(11)
        top_y_top = S(19)
        bottom_y_bottom = S(3)
        bottom_y_top = S(11)
    else:
        top_y_bottom = S(11)
        top_y_top = S(3)
        bottom_y_bottom = S(19)
        bottom_y_top = S(11)
    
    # --- Контуры колб ---
    top_path = NSBezierPath.bezierPath()
    if not flipped:
        top_path.moveToPoint_((S(4), S(19)))
        top_path.lineToPoint_((S(18), S(19)))
        top_path.lineToPoint_((S(12), S(11)))
        top_path.lineToPoint_((S(10), S(11)))
    else:
        top_path.moveToPoint_((S(4), S(3)))
        top_path.lineToPoint_((S(18), S(3)))
        top_path.lineToPoint_((S(12), S(11)))
        top_path.lineToPoint_((S(10), S(11)))
    top_path.closePath()
    
    bottom_path = NSBezierPath.bezierPath()
    if not flipped:
        bottom_path.moveToPoint_((S(10), S(11)))
        bottom_path.lineToPoint_((S(12), S(11)))
        bottom_path.lineToPoint_((S(18), S(3)))
        bottom_path.lineToPoint_((S(4), S(3)))
    else:
        bottom_path.moveToPoint_((S(10), S(11)))
        bottom_path.lineToPoint_((S(12), S(11)))
        bottom_path.lineToPoint_((S(18), S(19)))
        bottom_path.lineToPoint_((S(4), S(19)))
    bottom_path.closePath()
    
    # Стекло
    glass_color.set()
    top_path.fill()
    bottom_path.fill()
    
    # --- Песок с правильной физикой ---
    effective_fill = fill_ratio if not flipped else (1.0 - fill_ratio)
    
    # Верхний стакан
    if effective_fill > 0.02:
        max_top_height = abs(top_y_top - top_y_bottom)
        sand_height_top = max_top_height * effective_fill
        if not flipped:
            sand_rect_top = NSMakeRect(0, S(11), size, sand_height_top)
        else:
            sand_rect_top = NSMakeRect(0, S(3), size, sand_height_top)
        
        context = NSGraphicsContext.currentContext()
        context.saveGraphicsState()
        top_path.addClip()
        
        # Рисуем песок
        sand_color.set()
        NSBezierPath.fillRect_(sand_rect_top)
        
        # Добавляем обводку для песка, чтобы он не сливался
        outline_color.set()
        # Рисуем контур прямоугольника песка
        sand_outline = NSBezierPath.bezierPathWithRect_(sand_rect_top)
        sand_outline.setLineWidth_(S(0.8))
        sand_outline.stroke()
        
        context.restoreGraphicsState()
    
    # Нижний стакан
    if effective_fill < 0.98:
        bottom_fill = 1.0 - effective_fill
        max_bottom_height = abs(bottom_y_top - bottom_y_bottom)
        sand_height_bottom = max_bottom_height * bottom_fill
        if not flipped:
            sand_rect_bottom = NSMakeRect(0, S(3), size, sand_height_bottom)
        else:
            sand_rect_bottom = NSMakeRect(0, S(11), size, sand_height_bottom)
        
        context = NSGraphicsContext.currentContext()
        context.saveGraphicsState()
        bottom_path.addClip()
        
        # Рисуем песок
        sand_color.set()
        NSBezierPath.fillRect_(sand_rect_bottom)
        
        # Обводка песка
        outline_color.set()
        sand_outline_bottom = NSBezierPath.bezierPathWithRect_(sand_rect_bottom)
        sand_outline_bottom.setLineWidth_(S(0.8))
        sand_outline_bottom.stroke()
        
        context.restoreGraphicsState()
    
    # --- Обводка самих часов (контур колб) ---
    # Делаем обводку светлее, чтобы она выделялась на темной панели, но и на светлой тоже
    # В macOS темная панель -> нужен светлый контур. Светлая панель -> темный контур.
    # Используем серый цвет средней яркости.
    outline_color.set()
    top_path.setLineWidth_(S(1.2))
    top_path.stroke()
    bottom_path.setLineWidth_(S(1.2))
    bottom_path.stroke()
    
    # Перемычка
    mid_path = NSBezierPath.bezierPath()
    mid_path.moveToPoint_((S(9), S(11)))
    mid_path.lineToPoint_((S(13), S(11)))
    outline_color.set()
    mid_path.setLineWidth_(S(1.5))
    mid_path.stroke()
    
    img.unlockFocus()
    
    tiff_data = img.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff_data)
    png_data = rep.representationUsingType_properties_(4, None)
    png_data.writeToFile_atomically_(path, True)
    
    return path

def generate_app_icon(color_rgb, path="/tmp/notifyme_app_icon.png"):
    """Генерирует большую иконку (1024x1024) для приложения."""
    return generate_hourglass_icon(color_rgb, path=path, fill_ratio=0.5, flipped=False, blink=False, size=1024)
