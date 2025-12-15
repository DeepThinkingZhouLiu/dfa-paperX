"""PPTX to Image Converter

使用 LibreOffice 的 headless 模式将 PPTX 转换为图片。
"""

import os
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def convert_pptx_to_images(
    pptx_path: str,
    output_dir: Optional[str] = None,
    output_format: str = "png",
    dpi: int = 150,
) -> Tuple[bool, list[str]]:
    """将 PPTX 转换为图片
    
    使用 LibreOffice headless 模式先转换为 PDF，再使用 pdftoppm 转换为图片。
    
    Args:
        pptx_path: PPTX 文件路径
        output_dir: 输出目录，默认为 PPTX 所在目录
        output_format: 输出格式，支持 png, jpg
        dpi: 输出分辨率
        
    Returns:
        (success, list of image paths)
    """
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        log.error(f"PPTX file not found: {pptx_path}")
        return False, []
    
    if output_dir is None:
        output_dir = pptx_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建临时目录用于中间文件
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: 使用 LibreOffice 将 PPTX 转换为 PDF
        pdf_path = temp_path / f"{pptx_path.stem}.pdf"
        
        try:
            # 检查 libreoffice 是否可用
            result = subprocess.run(
                ["libreoffice", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log.error("LibreOffice is not installed or not in PATH")
                return False, []
        except FileNotFoundError:
            log.error("LibreOffice is not installed or not in PATH")
            return False, []
        
        log.info(f"Converting PPTX to PDF: {pptx_path}")
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(temp_path),
                str(pptx_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0 or not pdf_path.exists():
            log.error(f"Failed to convert PPTX to PDF: {result.stderr}")
            return False, []
        
        # Step 2: 使用 pdftoppm 或 pdf2image 将 PDF 转换为图片
        image_paths = []
        
        try:
            # 尝试使用 pdftoppm (更快)
            output_prefix = output_dir / pptx_path.stem
            
            cmd = [
                "pdftoppm",
                "-r", str(dpi),
            ]
            
            if output_format == "png":
                cmd.append("-png")
            elif output_format in ("jpg", "jpeg"):
                cmd.append("-jpeg")
            
            cmd.extend([str(pdf_path), str(output_prefix)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.warning(f"pdftoppm failed: {result.stderr}, trying pdf2image")
                raise FileNotFoundError("pdftoppm failed")
            
            # 查找生成的图片文件
            for f in sorted(output_dir.glob(f"{pptx_path.stem}-*.{output_format}")):
                image_paths.append(str(f))
            
            # 如果只有一页，重命名为更简洁的名称
            if len(image_paths) == 1:
                new_name = output_dir / f"{pptx_path.stem}.{output_format}"
                shutil.move(image_paths[0], new_name)
                image_paths = [str(new_name)]
                
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # 回退到 pdf2image (需要安装 pdf2image 和 poppler)
            try:
                from pdf2image import convert_from_path
                
                log.info("Using pdf2image for conversion")
                images = convert_from_path(str(pdf_path), dpi=dpi)
                
                for i, img in enumerate(images):
                    if len(images) == 1:
                        img_path = output_dir / f"{pptx_path.stem}.{output_format}"
                    else:
                        img_path = output_dir / f"{pptx_path.stem}-{i+1:02d}.{output_format}"
                    img.save(str(img_path), output_format.upper())
                    image_paths.append(str(img_path))
                    
            except ImportError:
                log.error("pdf2image is not installed. Install with: pip install pdf2image")
                return False, []
            except Exception as e:
                log.error(f"pdf2image conversion failed: {e}")
                return False, []
        
        log.info(f"Generated {len(image_paths)} image(s): {image_paths}")
        return True, image_paths

