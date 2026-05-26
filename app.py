import os
from pathlib import Path
import glob
import numpy as np
import cv2
from paddleocr import PaddleOCR
import re
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image
from datetime import datetime
import gradio as gr
import logging
from logging.handlers import RotatingFileHandler
import traceback

# ==================== CONFIG ====================
os.environ["FLAGS_use_mkldnn"] = "0"

# Use environment variable for root folder, default to /tmp for Azure
ROOT_FOLDER = os.getenv("ROOT_FOLDER", "/tmp/fuel_data")
os.makedirs(ROOT_FOLDER, exist_ok=True)

locations = ["{請選擇}", "CFD創富", "CWD柴灣", "SHD小蠔灣", "SWD上環", "TCD東涌", "TKD將軍澳", "TMD屯門", "WCD黃竹坑", "WKD西九"]
depot_gps = [("CFD創富", 22.272764832109846, 114.24250389449965),
        ("CWD柴灣", 22.270758379558714, 114.24155512333564),
        ("SHD小蠔灣", 22.315893212234425, 113.99856865402481),
        ("SWD上環", 22.288271040384796, 114.15105773910038),
        ("TCD東涌", 22.28009953657451, 113.9394554386798),
        ("TKD將軍澳", 22.316949281155114, 114.25819879997607),
        ("TMD屯門", 22.383505220952447, 113.96928212236955),
        ("WCD黃竹坑", 22.248418440612717, 114.16227259618798),
        ("WKD西九", 22.329873814418242, 114.14657647254528)]

car_ids = ["{請選擇}", "第1車", "第2車", "第3車", "第4車", "第5車"]
tank_ids = ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸", "第7缸", "第8缸"]

tank_list = {"CFD創富": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸", "第7缸", "第8缸"],
        "CWD柴灣": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸"],
        "SHD小蠔灣": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "SWD上環": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "TCD東涌": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "TKD將軍澳": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "TMD屯門": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "WCD黃竹坑": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"],
        "WKD西九": ["{請選擇}", "第1缸", "第2缸", "第3缸", "第4缸", "第5缸", "第6缸"]}

tab_names = ["油錶前", "油尺前", "封條1", "封條2", "油車前", "油車後", "油錶後", "油尺後", "收據"]
tab_list_S = {
        "{請選擇}": [],
        "CFD創富": ["油錶前", "油尺前", "封條1", "封條2", "油車前", "油車後", "油錶後", "油尺後", "收據"],
        "CWD柴灣": ["油錶前",  "封條1", "封條2", "油車前", "油車後", "油錶後", "收據"],
        "SHD小蠔灣": ["油尺前", "封條1", "封條2", "油車前", "油車後", "油尺後", "收據"],
        "SWD上環": ["油錶前",  "封條1", "封條2", "油車前", "油車後", "油錶後", "收據"],
        "TCD東涌": ["油尺前", "封條1", "封條2", "油車前", "油車後", "油尺後", "收據"],
        "TKD將軍澳": ["油尺前", "封條1", "封條2", "油車前", "油車後", "油尺後", "收據"],
        "TMD屯門": ["油尺前", "封條1", "封條2", "油車前", "油車後", "油尺後", "收據"],
        "WCD黃竹坑": ["油尺前", "封條1", "封條2", "油車前", "油車後", "油尺後", "收據"],
        "WKD西九": ["油錶前",  "封條1", "封條2", "油車前", "油車後", "油錶後", "收據"]}

required_tabs = ["油車前", "油車後"]
forced_check = False

# ==================== LOGGER SETUP ====================
logger = logging.getLogger("refuel_app")
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    handler.close()
    logger.removeHandler(handler)

logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(message)s")

class FlushingRotatingFileHandler(RotatingFileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

log_path = os.path.join(ROOT_FOLDER, "app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
file_handler = FlushingRotatingFileHandler(
    log_path,
    maxBytes=10_000_000,
    backupCount=5,
    encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

logger.info("Application started")

# ==================== OCR MODEL ====================
ocr_model = None
try:
    logger.info("Loading OCR model...")
    ocr_model = PaddleOCR(lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False, 
            enable_mkldnn=False)
    logger.info("OCR model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load OCR model: {str(e)}")
    logger.error(traceback.format_exc())

# ==================== FUNCTIONS ====================
def save_images(location, car_id, tank_id, *images):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uploaded_tabs = [tab_names[i] for i, img in enumerate(images) if img is not None]
        num_images = len(uploaded_tabs)
        logger.info(
            f"UPLOAD START | Location: {location} | Car: {car_id} | Tank: {tank_id} | "
            f"Uploaded tabs: {uploaded_tabs} ({num_images} images)"
        )

        if (not location or location == "{請選擇}" or not car_id or car_id == "{請選擇}" 
            or not tank_id or tank_id == "{請選擇}"):
            info_msg = "警告：確保已輸入地點，車號，缸號"
            logger.info(f"UPLOAD FAILED | Please select Location, Car ID, and Tank ID.")
            return info_msg

        prefix = f"{location}/{car_id}_{tank_id}"
        today = datetime.now().strftime("%Y-%m-%d")

        if required_tabs and forced_check:
            tab_dict = dict(zip(tab_names, images))
            missing = [tab for tab in required_tabs if not tab_dict.get(tab)]
            if missing:
                info_msg = f"警告：確保已輸入以下照片 {', '.join(missing)}"
                logger.info(f"UPLOAD FAILED | Missing images for required tabs: {', '.join(missing)}")
                return info_msg

        base_dir = os.path.join(ROOT_FOLDER, today, prefix)

        detected_tabs_exist = []
        if os.path.exists(base_dir):
            existing_files = os.listdir(base_dir)
            for f in existing_files:
                name, ext = os.path.splitext(f)
                detected_tabs_exist.append(name)
                if "油車前" in name.lower() and "油車前" not in detected_tabs_exist:
                    detected_tabs_exist.append("油車前")
                if "油車後" in name.lower() and "油車後" not in detected_tabs_exist:
                    detected_tabs_exist.append("油車後")
        else:
            os.makedirs(base_dir, exist_ok=True)

        return_msg = []
        saved_paths = []
        for i, img in enumerate(images):
            if img is None:
                continue
            if tab_names[i] in detected_tabs_exist:
                info_msg = f"跳過已上傳照片 {tab_names[i]}"
                return_msg.append(info_msg)
                logger.info(f"UPLOAD WARNING | Skipped uploaded image {tab_names[i]}")
                continue

            original_width, original_height = img.size
            new_width = int(original_width * (400 / original_height))
            img_resized = img.resize((new_width, 400))

            tab_name = tab_names[i]
            filename = f"{tab_name}.jpg"
            filepath = os.path.join(base_dir, filename)

            img_resized.save(filepath)
            saved_paths.append(filepath)
            logger.info(f"Saved image: {filepath}")

        if saved_paths:
            detected_tabs_exist = []
            if os.path.exists(base_dir):
                existing_files = os.listdir(base_dir)
                for f in existing_files:
                    name, ext = os.path.splitext(f)
                    detected_tabs_exist.append(name)
                    if "油車前" in name.lower() and "油車前" not in detected_tabs_exist:
                        detected_tabs_exist.append("油車前")
                    if "油車後" in name.lower() and "油車後" not in detected_tabs_exist:
                        detected_tabs_exist.append("油車後")

            missing = [tab for tab in required_tabs if tab not in detected_tabs_exist]

            if missing:
              info_msg = f"已上傳 {len(saved_paths)} 張新照片\n請上傳{', '.join(missing)}."
              return_msg.append(info_msg)
              logger.info(f"UPLOAD SUCCESS | Uploaded {len(saved_paths)} new images")
              return '\n'.join(return_msg)
            else:
              info_msg = f"已上傳 {len(saved_paths)} 張新照片"
              return_msg.append(info_msg)
              logger.info(f"UPLOAD SUCCESS | Uploaded {len(saved_paths)} new images")
              return '\n'.join(return_msg)
        else:
            info_msg = "警告：沒有新照片"
            return_msg.append(info_msg)
            logger.info(f"UPLOAD FAILED | No new image")
            return '\n'.join(return_msg)

    except Exception as e:
        logger.error(f"SUBMISSION EXCEPTION | Error: {str(e)}")
        logger.error(traceback.format_exc())
        return f"未知錯誤: {str(e)}"

def prefer_back_camera():
    custom_html = """
    <script>
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

    navigator.mediaDevices.getUserMedia = (constraints) => {
      if (!constraints.video.facingMode) {
        constraints.video.facingMode = {ideal: "environment"};
      }

      constraints.video.width = {exact: 400};
      constraints.video.height = {exact: 400};

      return originalGetUserMedia(constraints);
    };
    </script>
    """
    return custom_html

def nearest(gps):
    if "Allow" in gps:
        return "{請選擇}"
    try:
        lat, lon = map(float, gps.strip("[]").split(","))
        d = lambda c: (lat-c[1])**2 + (lon-c[2])**2
        return min(depot_gps, key=d)[0]
    except:
        return "{請選擇}"

def update_tank_dropdown(tank_id):
    tank_dropdown = tank_list.get(tank_id, ["{請選擇}"])
    return gr.Dropdown(choices=tank_dropdown, label="缸號", value=tank_dropdown[0], allow_custom_value=False, filterable=False, interactive=True)

def toggle_tabs(location, car, tank):
    updates = []
    active_tabs = tab_list_S.get(location, [])
    if location != "{請選擇}" and car != "{請選擇}" and tank != "{請選擇}":
        for tab in tab_names:
            if tab in active_tabs:
                updates.append(gr.update(visible=True))
            else:
                updates.append(gr.update(visible=False))
    else:
        for tab in tab_names:
            updates.append(gr.update(visible=False))
    return updates

def toggle_save(location, car, tank):
    if location != "{請選擇}" and car != "{請選擇}" and tank != "{請選擇}":
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)

def clear_images(selection):
    return [gr.update(value=None) for _ in tab_names]

# ==================== HISTORY FUNCTIONS ====================
def get_car_ids(date, location):
    try:
        date = datetime.fromtimestamp(date).strftime('%Y-%m-%d')
        base_path = f"{ROOT_FOLDER}/{date}/{location}"
        candidates = glob.glob(f"{base_path}/第*車_*", recursive=False)
        car_ids_list = [os.path.basename(c).split("_")[0] for c in candidates]
        return sorted(set(car_ids_list))
    except Exception as e:
        logger.error(f"Error getting car IDs: {str(e)}")
        return []

def update_car_dropdown(date, location):
    car_ids_list = get_car_ids(date, location)
    if car_ids_list:
        return gr.update(choices=car_ids_list, value=car_ids_list[0])
    else:
        return gr.update(choices=[], value=None)

def get_tank_names(date, location, id):
    try:
        date = datetime.fromtimestamp(date).strftime('%Y-%m-%d')
        base_path = f"{ROOT_FOLDER}/{date}/{location}"
        candidates = glob.glob(f"{base_path}/{id}_*", recursive=False)
        return [c.split("_")[-1] for c in candidates]
    except Exception as e:
        logger.error(f"Error getting tank names: {str(e)}")
        return []

def find_jpg_images(date, location, id, tank):
    try:
        date = datetime.fromtimestamp(date).strftime('%Y-%m-%d')
        pattern = f"{ROOT_FOLDER}/{date}/{location}/{id}_{tank}/**/*.jpg"
        files = sorted(glob.glob(pattern, recursive=True))
        return [(f, f"Tank {tank} - {os.path.basename(f)}") for f in files]
    except Exception as e:
        logger.error(f"Error finding JPG images: {str(e)}")
        return []

def assign_tanks(date, location, id):
    try:
        tanks = get_tank_names(date, location, id)
        galleries_data = []
        labels = []
        for i in range(4):
            if i < len(tanks):
                tank_name = tanks[i]
                galleries_data.append(find_jpg_images(date, location, id, tank_name))
                labels.append(f"Tank: {tank_name}")
            else:
                galleries_data.append([])
                labels.append("No Tank")
        msg = f"Found {len(tanks)} tank records: {', '.join(tanks)}" if tanks else "No tank records found"
        return galleries_data[0], labels[0], galleries_data[1], labels[1], galleries_data[2], labels[2], galleries_data[3], labels[3], msg
    except Exception as e:
        logger.error(f"Error assigning tanks: {str(e)}")
        return [], "No Tank", [], "No Tank", [], "No Tank", [], "No Tank", f"Error: {str(e)}"

# ==================== OCR PROCESSING ====================
def auto_adjust_brightness_contrast(img_cv, clip_limit=2.0, tile_grid_size=(8,8)):
    try:
        lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        l_adjusted = clahe.apply(l)
        lab_adjusted = cv2.merge([l_adjusted, a, b])
        adjusted_cv = cv2.cvtColor(lab_adjusted, cv2.COLOR_LAB2BGR)
        return adjusted_cv
    except Exception as e:
        logger.error(f"Error adjusting brightness: {str(e)}")
        return img_cv

def area(bbox):
    try:
        bbox = np.array(bbox, dtype=np.int64)
        x1, y1, x2, y2 = bbox
        return abs((x2-x1)*(y2-y1))
    except:
        return 0

# ==================== GRADIO INTERFACE ====================
def create_gradio_interface():
    with gr.Blocks(title="落油記錄工具", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 落油記錄工具")
        gr.Markdown("---")

        with gr.Tabs():
            # Module 1: 拍照 (Photo Recording)
            with gr.Tab("📸 拍照"):
                with gr.Row():
                    with gr.Column():
                        location_dropdown = gr.Dropdown(
                            choices=locations, 
                            label="地點", 
                            value=locations[0], 
                            allow_custom_value=False, 
                            filterable=False, 
                            interactive=True
                        )
                    with gr.Column():
                        car_dropdown = gr.Dropdown(
                            choices=car_ids, 
                            label="車號", 
                            value=car_ids[0], 
                            allow_custom_value=False, 
                            filterable=False
                        )
                    with gr.Column():
                        tank_dropdown = gr.Dropdown(
                            choices=["{請選擇}"], 
                            label="缸號", 
                            value="{請選擇}", 
                            allow_custom_value=False, 
                            filterable=False
                        )

                gr.Markdown("### 上傳照片")
                with gr.Tabs() as img_tabs:
                    image_inputs = []
                    tab_list = []
                    for tab_name in tab_names:
                        with gr.Tab(tab_name, visible=False) as tab:
                            img_input = gr.Image(
                                type="pil", 
                                label=f"上傳 {tab_name} 照片", 
                                height=400, 
                                sources=['webcam'], 
                                mirror_webcam=False, 
                                elem_id="camera_input"
                            )
                            image_inputs.append(img_input)
                            tab_list.append(tab)

                with gr.Row():
                    save_btn = gr.Button("💾 儲存所有照片", variant="primary", size="lg", visible=False)

                output_text = gr.Textbox(label="狀態", lines=4, interactive=False)

                save_btn.click(
                    fn=save_images,
                    inputs=[location_dropdown, car_dropdown, tank_dropdown] + image_inputs,
                    outputs=output_text
                )

                location_dropdown.change(toggle_tabs, [location_dropdown, car_dropdown, tank_dropdown], tab_list)
                car_dropdown.change(toggle_tabs, [location_dropdown, car_dropdown, tank_dropdown], tab_list)
                tank_dropdown.change(toggle_tabs, [location_dropdown, car_dropdown, tank_dropdown], tab_list)

                location_dropdown.change(toggle_save, [location_dropdown, car_dropdown, tank_dropdown], save_btn)
                car_dropdown.change(toggle_save, [location_dropdown, car_dropdown, tank_dropdown], save_btn)
                tank_dropdown.change(toggle_save, [location_dropdown, car_dropdown, tank_dropdown], save_btn)

                location_dropdown.change(clear_images, location_dropdown, image_inputs)
                car_dropdown.change(clear_images, location_dropdown, image_inputs)
                tank_dropdown.change(clear_images, location_dropdown, image_inputs)

                location_dropdown.change(fn=update_tank_dropdown, inputs=location_dropdown, outputs=tank_dropdown)

            # Module 2: 記錄 (History)
            with gr.Tab("📋 記錄"):
                with gr.Row():
                    with gr.Column():
                        date_picker = gr.DateTime(
                            label="日期", 
                            include_time=False, 
                            value=datetime.now().date().isoformat()
                        )
                    with gr.Column():
                        location_dropdown2 = gr.Dropdown(
                            choices=locations, 
                            label="地點", 
                            value=locations[0]
                        )
                    with gr.Column():
                        car_dropdown2 = gr.Dropdown(
                            choices=[], 
                            label="車號", 
                            value=None
                        )

                tank_message = gr.Textbox(label="坦克摘要", interactive=False, lines=2)

                with gr.Row():
                    with gr.Column():
                        tank_label1 = gr.Textbox(label="坦克信息 1", interactive=False)
                        gallery1 = gr.Gallery(columns=4, label="坦克 1 圖片")
                    with gr.Column():
                        tank_label2 = gr.Textbox(label="坦克信息 2", interactive=False)
                        gallery2 = gr.Gallery(columns=4, label="坦克 2 圖片")

                with gr.Row():
                    with gr.Column():
                        tank_label3 = gr.Textbox(label="坦克信息 3", interactive=False)
                        gallery3 = gr.Gallery(columns=4, label="坦克 3 圖片")
                    with gr.Column():
                        tank_label4 = gr.Textbox(label="坦克信息 4", interactive=False)
                        gallery4 = gr.Gallery(columns=4, label="坦克 4 圖片")

                def update_all(date, location, car):
                    if car is None:
                        return [], "No Tank", [], "No Tank", [], "No Tank", [], "No Tank", "請選擇車號"
                    g1, l1, g2, l2, g3, l3, g4, l4, msg = assign_tanks(date, location, car)
                    return g1, l1, g2, l2, g3, l3, g4, l4, msg

                date_picker.change(update_car_dropdown, [date_picker, location_dropdown2], car_dropdown2)
                location_dropdown2.change(update_car_dropdown, [date_picker, location_dropdown2], car_dropdown2)

                date_picker.change(update_all, [date_picker, location_dropdown2, car_dropdown2],
                                  [gallery1, tank_label1, gallery2, tank_label2, gallery3, tank_label3, gallery4, tank_label4, tank_message])
                location_dropdown2.change(update_all, [date_picker, location_dropdown2, car_dropdown2],
                                          [gallery1, tank_label1, gallery2, tank_label2, gallery3, tank_label3, gallery4, tank_label4, tank_message])
                car_dropdown2.change(update_all, [date_picker, location_dropdown2, car_dropdown2],
                                    [gallery1, tank_label1, gallery2, tank_label2, gallery3, tank_label3, gallery4, tank_label4, tank_message])

            # Module 3: 關於 (About)
            with gr.Tab("ℹ️ 關於"):
                gr.Markdown("""
                ## 落油記錄工具
                
                本應用程序用於記錄和管理油田測量數據。
                
                **功能：**
                - 📸 拍照並上傳油田測量照片
                - 📋 查看歷史記錄和相冊
                - 🔍 OCR 識別測量數值
                - 💾 自動保存和組織數據
                
                **使用說明：**
                1. 在"拍照"標籤頁選擇地點、車號和缸號
                2. 為每個類別上傳相應的照片
                3. 點擊"儲存所有照片"保存數據
                4. 在"記錄"標籤頁查看歷史數據
                
                **支持的地點：**
                - CFD創富
                - CWD柴灣
                - SHD小蠔灣
                - SWD上環
                - TCD東涌
                - TKD將軍澳
                - TMD屯門
                - WCD黃竹坑
                - WKD西九
                
                ---
                版本 1.0.0 | 2026-05-22
                """)

        demo.css = """
        #camera_input button {
            transform: scale(2);
        }
        """
        
        return demo

if __name__ == "__main__":
    try:
        # Create Gradio interface
        demo = create_gradio_interface()
        
        # Get port from environment or default to 7860
        port = int(os.getenv("PORT", "7860"))
        
        logger.info(f"Starting Gradio server on port {port}")
        
        # Launch Gradio with Azure App Services compatible settings
        demo.launch(
            server_name="0.0.0.0",
            server_port=port,
            share=False,
            debug=False,
            show_error=True,
            allowed_paths=[ROOT_FOLDER]
        )
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        logger.error(traceback.format_exc())
        raise
