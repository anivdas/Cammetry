from __future__ import annotations

import csv
import json
import math
import os
import platform
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2  # type: ignore
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk

from tts_core import (
    APP_NAME, APP_VERSION, AUTOPILOT_NAMES, CAMERA_LABELS, CAMERA_ORDER, CAMERA_WALL_ORDER,
    ClipGroup, TelemetrySample, choose_telemetry_source, discover_clips, export_csv,
    load_telemetry, probe_video, detect_teslacam_roots,
)
from tts_export import BlurZone, ExportOptions, available_encoders, export_video
from tts_locales import LANGUAGES, tr, trf, camera_label, assist_label, event_reason_label
from tts_player import MultiCameraPlayer
from tts_map import MapMosaic, build_osm_mosaic, OSM_ATTRIBUTION
from tts_settings import load_settings, save_settings, settings_dir

BG = "#0b0f14"
PANEL = "#111821"
CARD = "#161f29"
CARD2 = "#1b2632"
TEXT = "#edf3f8"
MUTED = "#8b99a8"
ACCENT = "#3b82f6"
ACCENT2 = "#22d3ee"
FSD = "#3b82f6"
MANUAL = "#6b7280"
WARN = "#f6b73c"
DANGER = "#ef5b5b"
GOOD = "#37c978"
BORDER = "#263342"

LAYOUT_KEYS = {"Six Camera": "six_camera", "Four Camera": "four_camera", "Single Camera": "single_camera"}
QUALITY_KEYS = {"Mobile": "mobile", "Medium": "medium", "High": "high", "Maximum": "maximum"}
DASHBOARD_STYLE_KEYS = {"Default": "default", "Compact": "compact"}
DASHBOARD_SIZE_KEYS = {"Small": "small", "Medium": "medium", "Large": "large", "X-Large": "xlarge"}
MAP_MODE_KEYS = {"Local Grid (offline)": "map_offline", "OpenStreetMap (online)": "map_osm"}

BROWSE_TESLACAM_LABELS = {
    "English": "Browse TeslaCam…",
    "Spanish": "Buscar TeslaCam…",
    "French": "Parcourir TeslaCam…",
    "German": "TeslaCam durchsuchen…",
    "Chinese (Simplified)": "浏览 TeslaCam…",
    "Japanese": "TeslaCamを参照…",
    "Korean": "TeslaCam 찾아보기…",
    "Portuguese": "Procurar TeslaCam…",
    "Russian": "Обзор TeslaCam…",
    "Italian": "Sfoglia TeslaCam…",
    "Dutch": "TeslaCam bladeren…",
    "Polish": "Przeglądaj TeslaCam…",
    "Turkish": "TeslaCam gözat…",
}


def localized_choice(language: str, canonical: str, mapping: dict[str, str]) -> str:
    key = mapping.get(canonical)
    return tr(language, key) if key else canonical


def canonical_choice(language: str, displayed: str, mapping: dict[str, str]) -> str:
    for canonical, key in mapping.items():
        if displayed == canonical or displayed == tr(language, key):
            return canonical
    return displayed


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(int(m), 60)
    if h:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


def flat_button(parent, text, command, accent=False, width=None, danger=False):
    bg = ACCENT if accent else DANGER if danger else CARD2
    active = "#4b8ff8" if accent else "#f06b6b" if danger else "#243242"
    b = tk.Button(parent, text=text, command=command, bg=bg, fg="white", activebackground=active,
        activeforeground="white", relief="flat", bd=0, padx=12, pady=7,
        font=("Segoe UI Semibold", 9), cursor="hand2", highlightthickness=0)
    if width: b.configure(width=width)
    return b


class CameraTile(tk.Frame):
    def __init__(self, parent, camera: str, click_cb, language: str = "English"):
        super().__init__(parent, bg="#05080b", highlightthickness=1, highlightbackground=BORDER)
        self.camera=camera; self.language=language; self.click_cb=click_cb; self.photo=None
        self.header=tk.Label(self,text=camera_label(language,camera),bg="#0a1017",fg="#c7d2de",font=("Segoe UI Semibold",9),anchor="w",padx=8,pady=4); self.header.pack(fill="x")
        self.image=tk.Label(self,bg="#030506",fg=MUTED,text=tr(language,"no_camera"),font=("Segoe UI",9)); self.image.pack(fill="both",expand=True)
        for widget in (self,self.header,self.image): widget.bind("<Button-1>",lambda _e,c=camera:self.click_cb(c)); widget.configure(cursor="hand2")
    def set_active(self, active: bool, triggered: bool=False):
        color=DANGER if triggered else ACCENT if active else BORDER; self.configure(highlightbackground=color,highlightcolor=color,highlightthickness=2 if active or triggered else 1); self.header.configure(fg="#ffffff" if active else "#c7d2de")
    def set_placeholder(self,text=None): self.photo=None; self.image.configure(image="",text=text or tr(self.language,"not_available"))
    def set_frame(self,frame,max_size:Tuple[int,int]):
        if frame is None: self.set_placeholder(); return
        w,h=max_size
        if w<=10 or h<=10:return
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); ih,iw=rgb.shape[:2]; scale=min(w/iw,h/ih); nw,nh=max(1,int(iw*scale)),max(1,int(ih*scale)); resized=cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_AREA); img=Image.fromarray(resized); canvas=Image.new("RGB",(w,h),(3,5,6)); canvas.paste(img,((w-nw)//2,(h-nh)//2)); self.photo=ImageTk.PhotoImage(canvas); self.image.configure(image=self.photo,text="")


class TimelineCanvas(tk.Canvas):
    def __init__(self,parent,seek_cb,language:str="English"):
        super().__init__(parent,height=72,bg="#0b1118",highlightthickness=1,highlightbackground=BORDER,cursor="hand2")
        self.language=language; self.samples=[]; self.fps=36.0; self.duration=0.0; self.position=0.0; self.in_point=0.0; self.out_point=0.0; self.event_time=None; self.review_events=[]; self.seek_cb=seek_cb
        self.bind("<Button-1>",self._seek_event); self.bind("<B1-Motion>",self._seek_event); self.bind("<Configure>",lambda _e:self.redraw())
    def set_data(self,samples,fps,duration,event_time=None): self.samples=samples or []; self.fps=fps or 36.0; self.duration=max(0.0,duration); self.event_time=event_time; self.redraw()
    def set_position(self,pos): self.position=pos; self.redraw(position_only=False)
    def set_trim(self,in_point,out_point): self.in_point,self.out_point=in_point,out_point; self.redraw()
    def set_review_events(self,events): self.review_events=list(events or []); self.redraw()
    def _seek_event(self,event):
        if self.duration<=0:return
        x=max(0,min(self.winfo_width(),event.x)); self.seek_cb(x/max(1,self.winfo_width())*self.duration)
    def redraw(self,position_only=False):
        self.delete("all"); w,h=max(1,self.winfo_width()),max(1,self.winfo_height()); self.create_rectangle(0,0,w,h,fill="#0b1118",outline="")
        if self.duration<=0: self.create_text(12,h//2,text=tr(self.language,"timeline"),fill=MUTED,anchor="w",font=("Segoe UI",9)); return
        y0,y1=18,h-18; self.create_line(0,(y0+y1)//2,w,(y0+y1)//2,fill="#293746",width=2)
        if self.samples:
            step=max(1,len(self.samples)//max(1,w))
            for x in range(w):
                idx=min(len(self.samples)-1,x*step); s=self.samples[idx]
                if s.autopilot_state:self.create_line(x,y1-7,x,y1,fill=FSD)
                if s.brake_applied:self.create_line(x,y0,x,y0+8,fill=DANGER)
                elif s.blinker_on_left or s.blinker_on_right:self.create_line(x,y0,x,y0+6,fill=WARN)
        if self.event_time is not None and 0<=self.event_time<=self.duration:
            ex=self.event_time/self.duration*w; self.create_line(ex,0,ex,h,fill=WARN,width=2); self.create_text(ex+4,4,text=tr(self.language,"event_marker"),fill=WARN,anchor="nw",font=("Segoe UI Semibold",7))
        for marker in self.review_events:
            seconds=float(getattr(marker,"seconds",-1.0)); severity=int(getattr(marker,"severity",1))
            if 0<=seconds<=self.duration:
                mx=seconds/self.duration*w; color=DANGER if severity>=3 else WARN if severity==2 else "#73b7ff"
                self.create_line(mx,y0-2,mx,y1+2,fill=color,width=1)
                self.create_polygon(mx-3,y0-3,mx+3,y0-3,mx,y0+2,fill=color,outline="")
        if self.out_point>self.in_point:
            x0=self.in_point/self.duration*w; x1=self.out_point/self.duration*w; self.create_rectangle(x0,0,x1,h,outline=GOOD,width=1); self.create_text(x0+3,h-3,text=tr(self.language,"in_marker"),fill=GOOD,anchor="sw",font=("Segoe UI Semibold",7)); self.create_text(x1-3,h-3,text=tr(self.language,"out_marker"),fill=DANGER,anchor="se",font=("Segoe UI Semibold",7))
        px=max(0,min(w,self.position/self.duration*w)); self.create_line(px,0,px,h,fill="#ffffff",width=2)


class RouteCanvas(tk.Canvas):
    def __init__(self,parent,language="English",map_mode="Local Grid (offline)",cache_dir=None):
        super().__init__(parent,bg="#0c1219",height=190,highlightthickness=0); self.language=language; self.map_mode=map_mode; self.cache_dir=cache_dir or (Path.home()/".cammetry-map-cache"); self.samples=[]; self.fps=36.0; self.position=0.0; self.zoom=1.0; self.pan_x=0.0; self.pan_y=0.0; self._pan_start=None; self.map_mosaic=None; self.map_photo=None; self._map_queue=queue.Queue(); self._map_token=0; self.empty_text=tr(language,"no_clip_selected")
        self.bind("<Configure>",lambda _e:self.redraw()); self.bind("<MouseWheel>",self._wheel); self.bind("<ButtonPress-3>",self._pan_begin); self.bind("<B3-Motion>",self._pan_move); self.after(200,self._poll_map)
    def set_data(self,samples,fps):
        self.samples=samples or []; self.fps=fps or 36.0; self.map_mosaic=None; self.map_photo=None; self.zoom=1.0; self.pan_x=self.pan_y=0.0; self._map_token+=1; token=self._map_token
        if self.map_mode.startswith("OpenStreetMap") and self.samples:
            def work():
                try:self._map_queue.put((token,build_osm_mosaic(self.samples,self.cache_dir)))
                except Exception as exc:self._map_queue.put((token,exc))
            threading.Thread(target=work,daemon=True).start()
        self.redraw()
    def set_empty_text(self,text):
        self.empty_text=text; self.redraw()
    def _poll_map(self):
        try:
            while True:
                token,result=self._map_queue.get_nowait()
                if token!=self._map_token:continue
                if isinstance(result,MapMosaic):self.map_mosaic=result
                self.redraw()
        except queue.Empty:pass
        try:self.after(200,self._poll_map)
        except tk.TclError:pass
    def set_position(self,pos):self.position=pos;self.redraw()
    def _wheel(self,event):self.zoom=max(.7,min(8.0,self.zoom*(1.18 if event.delta>0 else 1/1.18)));self.redraw()
    def _pan_begin(self,event):self._pan_start=(event.x,event.y,self.pan_x,self.pan_y)
    def _pan_move(self,event):
        if not self._pan_start:return
        x0,y0,px,py=self._pan_start;self.pan_x=px+(event.x-x0);self.pan_y=py+(event.y-y0);self.redraw()
    def _map_transform(self,w,h):
        if not self.map_mosaic:return None
        img=self.map_mosaic.image;base=min(w/max(1,img.width),h/max(1,img.height));scale=base*self.zoom;dw,dh=max(1,int(img.width*scale)),max(1,int(img.height*scale));x0=(w-dw)/2+self.pan_x;y0=(h-dh)/2+self.pan_y;return scale,x0,y0,dw,dh
    def redraw(self):
        self.delete("all");w,h=max(10,self.winfo_width()),max(10,self.winfo_height());valid=[(i,s) for i,s in enumerate(self.samples) if abs(s.latitude_deg)>1e-8 or abs(s.longitude_deg)>1e-8]
        if len(valid)<2:
            for x in range(0,w,50):self.create_line(x,0,x,h,fill="#151e28")
            for y in range(0,h,50):self.create_line(0,y,w,y,fill="#151e28")
            self.create_text(w//2,h//2,text=self.empty_text,fill=MUTED,font=("Segoe UI",9));return
        transform=self._map_transform(w,h)
        if transform and self.map_mosaic:
            scale,x0,y0,dw,dh=transform;img=self.map_mosaic.image.resize((dw,dh),Image.Resampling.LANCZOS);self.map_photo=ImageTk.PhotoImage(img);self.create_image(x0,y0,image=self.map_photo,anchor="nw");self.create_rectangle(0,0,w,h,fill="#071019",stipple="gray25",outline="")
            def pt(sample):
                px,py=self.map_mosaic.pixel(sample.longitude_deg,sample.latitude_deg);return x0+px*scale,y0+py*scale
        else:
            for x in range(0,w,50):self.create_line(x,0,x,h,fill="#151e28")
            for y in range(0,h,50):self.create_line(0,y,w,y,fill="#151e28")
            lons=[s.longitude_deg for _,s in valid];lats=[s.latitude_deg for _,s in valid];minx,maxx=min(lons),max(lons);miny,maxy=min(lats),max(lats);dx=max(maxx-minx,1e-9);dy=max(maxy-miny,1e-9);pad=15
            def pt(sample):
                x=pad+(sample.longitude_deg-minx)/dx*(w-2*pad);y=h-pad-(sample.latitude_deg-miny)/dy*(h-2*pad);cx,cy=w/2,h/2;return (x-cx)*self.zoom+cx+self.pan_x,(y-cy)*self.zoom+cy+self.pan_y
        prev=None
        for _,sample in valid:
            p=pt(sample)
            if prev:self.create_line(prev[0],prev[1],p[0],p[1],fill=FSD if sample.autopilot_state else MANUAL,width=3,smooth=True)
            prev=p
        idx=min(len(self.samples)-1,max(0,int(round(self.position*self.fps))));sample=self.samples[idx]
        if abs(sample.latitude_deg)>1e-8 or abs(sample.longitude_deg)>1e-8:
            p=pt(sample);self.create_oval(p[0]-5,p[1]-5,p[0]+5,p[1]+5,fill="#ffffff",outline=ACCENT,width=2)
        if self.map_mosaic:self.create_text(8,h-8,text=OSM_ATTRIBUTION,fill="#d4d9de",anchor="sw",font=("Segoe UI",7))
        self.create_text(8,8,text=tr(self.language,"local_gps_route")+"  •  wheel zoom  •  right-drag pan",fill=MUTED,anchor="nw",font=("Segoe UI",7))


class BlurZoneDialog(tk.Toplevel):
    def __init__(self,parent,image,initial,strength=12,language="English"):
        super().__init__(parent);self.language=language;self.title(tr(language,"blur_zones"));self.configure(bg=BG);self.geometry("900x650");self.transient(parent);self.result=None;self.strength=strength;self.zones=[BlurZone(z.x,z.y,z.w,z.h,z.strength) for z in initial];self.image_src=image
        self.canvas=tk.Canvas(self,bg="#05080b",highlightthickness=0,cursor="crosshair");self.canvas.pack(fill="both",expand=True,padx=14,pady=(14,8));bar=tk.Frame(self,bg=BG);bar.pack(fill="x",padx=14,pady=(0,14));tk.Label(bar,text=tr(language,"privacy_blur_help"),bg=BG,fg=MUTED,font=("Segoe UI",9)).pack(side="left");flat_button(bar,tr(language,"clear_trim"),self.clear).pack(side="right",padx=4);flat_button(bar,tr(language,"cancel"),self.cancel).pack(side="right",padx=4);flat_button(bar,tr(language,"save"),self.accept,accent=True).pack(side="right",padx=4);self.tk_img=None;self.disp_rect=(0,0,1,1);self.drag_start=None;self.temp_rect=None;self.canvas.bind("<Configure>",lambda _e:self.redraw());self.canvas.bind("<Button-1>",self.start_drag);self.canvas.bind("<B1-Motion>",self.drag);self.canvas.bind("<ButtonRelease-1>",self.end_drag);self.grab_set()
    def redraw(self):
        self.canvas.delete("all");cw,ch=max(10,self.canvas.winfo_width()),max(10,self.canvas.winfo_height());iw,ih=self.image_src.size;scale=min(cw/iw,ch/ih);dw,dh=max(1,int(iw*scale)),max(1,int(ih*scale));x=(cw-dw)//2;y=(ch-dh)//2;img=self.image_src.resize((dw,dh),Image.Resampling.LANCZOS);self.tk_img=ImageTk.PhotoImage(img);self.canvas.create_image(x,y,image=self.tk_img,anchor="nw");self.disp_rect=(x,y,dw,dh)
        for z in self.zones:self.canvas.create_rectangle(x+z.x*dw,y+z.y*dh,x+(z.x+z.w)*dw,y+(z.y+z.h)*dh,outline=DANGER,width=2,fill="",dash=(5,3))
    def start_drag(self,e):self.drag_start=(e.x,e.y)
    def drag(self,e):
        if not self.drag_start:return
        if self.temp_rect:self.canvas.delete(self.temp_rect)
        self.temp_rect=self.canvas.create_rectangle(self.drag_start[0],self.drag_start[1],e.x,e.y,outline=DANGER,width=2,dash=(4,2))
    def end_drag(self,e):
        if not self.drag_start:return
        x,y,dw,dh=self.disp_rect;x0,y0=self.drag_start;x1,y1=e.x,e.y;self.drag_start=None;left=max(x,min(x0,x1));top=max(y,min(y0,y1));right=min(x+dw,max(x0,x1));bottom=min(y+dh,max(y0,y1))
        if right-left>8 and bottom-top>8:self.zones.append(BlurZone((left-x)/dw,(top-y)/dh,(right-left)/dw,(bottom-top)/dh,self.strength))
        self.temp_rect=None;self.redraw()
    def clear(self):self.zones=[];self.redraw()
    def accept(self):self.result=self.zones;self.destroy()
    def cancel(self):self.result=None;self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title(f"{APP_NAME} {APP_VERSION}");self.geometry("1500x940");self.minsize(1180,760);self.configure(bg=BG);self.settings=load_settings();self.language=self.settings.get("language","English");self.root_path=tk.StringVar(value=self.settings.get("default_folder",""))
        self.filter_kind = "All"
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr(self.language, "open_folder_status"))
        self.groups: List[ClipGroup] = []
        self.filtered_groups: List[ClipGroup] = []
        self.selected_group: Optional[ClipGroup] = None
        self.samples: List[TelemetrySample] = []
        self.telemetry_fps = 36.0
        self.video_duration = 0.0
        self.active_camera = "front"
        self.triggered_camera: Optional[str] = None
        self.player = MultiCameraPlayer()
        self.last_frames: Dict[str, object] = {}
        self.in_point = 0.0
        self.out_point = 0.0
        self.blur_zones: List[BlurZone] = []
        self.last_output: Optional[Path] = None
        self.export_toast: Optional[tk.Toplevel] = None
        self.export_toast_progress = None
        self.export_toast_label = None
        self._load_token = 0
        self._worker_q: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self._last_preview_update = 0.0
        self.preview_layout = tk.StringVar(value=localized_choice(self.language, "Six Camera", LAYOUT_KEYS))
        self.play_speed = tk.DoubleVar(value=1.0)
        self._apply_window_icon()
        self._setup_style()
        self._build_ui()
        self._bind_shortcuts()
        self.after(40, self._tick)
        self.after(100, self._poll_worker)
        if self.root_path.get() and Path(self.root_path.get()).exists():
            self.after(250, self.scan)
        else:
            self.after(350, lambda: self.auto_detect_root(silent=True))
        if self.settings.get("check_updates") and self.settings.get("update_repo"):
            self.after(1500, lambda: self.check_updates(False))
        if not self.settings.get("privacy_notice_seen"):
            self.after(700, self._first_run_notice)

    def destroy(self):
        self.player.release()
        super().destroy()

    def t(self,key): return tr(self.language,key)
    def tf(self,key,**kwargs): return trf(self.language,key,**kwargs)

    def _apply_window_icon(self):
        if os.name != "nt":
            return
        try:
            base=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
            icon=base/"assets"/"app.ico"
            if icon.exists():
                self.iconbitmap(default=str(icon))
        except Exception:
            pass

    def _setup_style(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Dark.Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=34,borderwidth=0,font=("Segoe UI",9))
        style.map("Dark.Treeview",background=[("selected","#1e3a5f")],foreground=[("selected","white")])
        style.configure("Dark.Treeview.Heading",background=CARD2,foreground=MUTED,relief="flat",font=("Segoe UI Semibold",8))
        style.configure("Dark.Horizontal.TProgressbar",troughcolor="#0c1218",background=ACCENT,bordercolor="#0c1218",lightcolor=ACCENT,darkcolor=ACCENT)
        style.configure("Dark.TCombobox",fieldbackground=CARD2,background=CARD2,foreground=TEXT,arrowcolor=TEXT,borderwidth=0)
        style.configure("Dark.Vertical.TScrollbar",background=CARD2,troughcolor=PANEL,bordercolor=BORDER,arrowcolor=TEXT,relief="flat",width=12)
        style.map("Dark.Vertical.TScrollbar",background=[("active","#2a3949"),("pressed","#33475a")])
        style.map("Dark.TCombobox",fieldbackground=[("readonly",CARD2)],background=[("readonly",CARD2)],foreground=[("readonly",TEXT)],selectbackground=[("readonly",CARD2)],selectforeground=[("readonly",TEXT)])

    def _build_ui(self):
        self._build_topbar()
        body=tk.Frame(self,bg=BG); body.pack(fill="both",expand=True,padx=12,pady=(0,8))
        body.grid_columnconfigure(0,minsize=280,weight=0); body.grid_columnconfigure(1,weight=1); body.grid_columnconfigure(2,minsize=330,weight=0); body.grid_rowconfigure(0,weight=1)
        self.left=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); self.left.grid(row=0,column=0,sticky="nsew",padx=(0,8))
        self.center=tk.Frame(body,bg=BG); self.center.grid(row=0,column=1,sticky="nsew",padx=0)
        self.right=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); self.right.grid(row=0,column=2,sticky="nsew",padx=(8,0))
        self._build_left(); self._build_center(); self._build_right(); self._build_bottom()

    def _build_topbar(self):
        bar=tk.Frame(self,bg=BG,height=58); bar.pack(fill="x",padx=12,pady=(10,8)); bar.pack_propagate(False)
        brand=tk.Frame(bar,bg=BG); brand.pack(side="left",fill="y")
        tk.Label(brand,text="CAMMETRY",bg=BG,fg=TEXT,font=("Segoe UI Semibold",15)).pack(anchor="w")
        tk.Label(brand,text=self.t("brand_subtitle"),bg=BG,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w")
        pathbox=tk.Frame(bar,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); pathbox.pack(side="left",fill="x",expand=True,padx=18,pady=5)
        self.path_entry=tk.Entry(pathbox,textvariable=self.root_path,bg=PANEL,fg=TEXT,insertbackground="white",relief="flat",bd=0,font=("Segoe UI",9)); self.path_entry.pack(side="left",fill="x",expand=True,padx=10,pady=7)
        flat_button(pathbox,BROWSE_TESLACAM_LABELS.get(self.language,"Browse TeslaCam…"),self.browse_root,accent=True).pack(side="right",padx=4,pady=3)
        flat_button(pathbox,self.t("auto_detect"),self.auto_detect_root).pack(side="right",padx=2,pady=3)
        flat_button(bar,"⚙",self.open_settings,width=3).pack(side="right",padx=4,pady=8)
        flat_button(bar,"?",self.open_support,width=3).pack(side="right",padx=4,pady=8)

    def _build_left(self):
        top=tk.Frame(self.left,bg=PANEL); top.pack(fill="x",padx=10,pady=(10,6))
        tk.Label(top,text=self.t("events").upper(),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",10)).pack(side="left")
        self.count_label=tk.Label(top,text="0",bg=PANEL,fg=MUTED,font=("Segoe UI",9)); self.count_label.pack(side="right")
        tabs=tk.Frame(self.left,bg=PANEL); tabs.pack(fill="x",padx=8,pady=(0,6)); self.filter_buttons={}
        for kind,key in (("All","all"),("Recent","recent"),("Sentry","sentry"),("Saved","saved")):
            b=flat_button(tabs,self.t(key),lambda k=kind:self.set_filter(k)); b.pack(side="left",padx=2); self.filter_buttons[kind]=b
        searchbox=tk.Frame(self.left,bg="#0c1218",highlightthickness=1,highlightbackground=BORDER); searchbox.pack(fill="x",padx=10,pady=(2,8))
        e=tk.Entry(searchbox,textvariable=self.search_var,bg="#0c1218",fg=TEXT,insertbackground="white",relief="flat",bd=0,font=("Segoe UI",9)); e.pack(fill="x",padx=8,pady=7); e.bind("<KeyRelease>",lambda _e:self.refresh_event_list())
        cols=("time","type","trigger","cams")
        self.event_tree=ttk.Treeview(self.left,columns=cols,show="headings",selectmode="browse",style="Dark.Treeview")
        self.event_tree.heading("time",text=self.t("recorded").upper()); self.event_tree.heading("type",text=self.t("type").upper()); self.event_tree.heading("trigger",text=self.t("trigger").upper()); self.event_tree.heading("cams",text=self.t("cams").upper())
        self.event_tree.column("time",width=132,anchor="w"); self.event_tree.column("type",width=58,anchor="center"); self.event_tree.column("trigger",width=105,anchor="w"); self.event_tree.column("cams",width=42,anchor="center")
        treebox=tk.Frame(self.left,bg=PANEL); treebox.pack(fill="both",expand=True,padx=8,pady=(0,8))
        event_scroll=ttk.Scrollbar(treebox,orient="vertical",command=self.event_tree.yview,style="Dark.Vertical.TScrollbar"); self.event_tree.configure(yscrollcommand=event_scroll.set)
        event_scroll.pack(side="right",fill="y"); self.event_tree.pack(side="left",fill="both",expand=True); self.event_tree.bind("<<TreeviewSelect>>",self.on_event_select)
        foot=tk.Frame(self.left,bg=PANEL); foot.pack(fill="x",padx=8,pady=(0,8))
        flat_button(foot,self.t("delete"),self.delete_selected,danger=True).pack(side="left")
        flat_button(foot,self.t("scan"),self.scan).pack(side="right")

    def _build_center(self):
        toolbar=tk.Frame(self.center,bg=BG); toolbar.pack(fill="x",pady=(0,7))
        self.clip_title=tk.Label(toolbar,text=self.t("no_clip"),bg=BG,fg=TEXT,font=("Segoe UI Semibold",11),anchor="w"); self.clip_title.pack(side="left",fill="x",expand=True)
        self.layout_combo=ttk.Combobox(toolbar,textvariable=self.preview_layout,values=tuple(localized_choice(self.language, c, LAYOUT_KEYS) for c in LAYOUT_KEYS),state="readonly",width=15,style="Dark.TCombobox"); self.layout_combo.pack(side="right"); self.layout_combo.bind("<<ComboboxSelected>>",lambda _e:self.update_camera_layout())
        self.wall=tk.Frame(self.center,bg="#030506"); self.wall.pack(fill="both",expand=True)
        self.tiles={c:CameraTile(self.wall,c,self.set_active_camera,self.language) for c in CAMERA_WALL_ORDER}
        self.update_camera_layout()
        controls=tk.Frame(self.center,bg=BG); controls.pack(fill="x",pady=(8,5))
        self.play_button=flat_button(controls,"▶  "+self.t("play"),self.toggle_play,accent=True); self.play_button.pack(side="left")
        seek=int(self.settings.get("seek_seconds",10)); flat_button(controls,f"◀ {seek}s",lambda:self.skip(-seek)).pack(side="left",padx=(6,2)); flat_button(controls,f"{seek}s ▶",lambda:self.skip(seek)).pack(side="left",padx=2)
        tk.Label(controls,text=self.t("playback_speed"),bg=BG,fg=MUTED,font=("Segoe UI",8)).pack(side="left",padx=(14,4))
        self.speed_combo=ttk.Combobox(controls,textvariable=self.play_speed,values=(0.5,1.0,2.0,4.0),state="readonly",width=5,style="Dark.TCombobox"); self.speed_combo.pack(side="left"); self.speed_combo.bind("<<ComboboxSelected>>",lambda _e:self.player.set_speed(self.play_speed.get()))
        self.time_label=tk.Label(controls,text="00:00.00 / 00:00.00",bg=BG,fg=MUTED,font=("Consolas",9)); self.time_label.pack(side="right")
        self.timeline=TimelineCanvas(self.center,self.seek,self.language); self.timeline.pack(fill="x",pady=(0,5))
        trbar=tk.Frame(self.center,bg=BG); trbar.pack(fill="x")
        flat_button(trbar,self.t("set_in"),self.set_in).pack(side="left",padx=(0,4)); flat_button(trbar,self.t("set_out"),self.set_out).pack(side="left",padx=4); flat_button(trbar,self.t("clear_trim"),self.clear_trim).pack(side="left",padx=4)
        self.trim_label=tk.Label(trbar,text=self.t("trim_full"),bg=BG,fg=MUTED,font=("Segoe UI",8)); self.trim_label.pack(side="left",padx=10)
        flat_button(trbar,self.t("snapshot"),self.save_snapshot).pack(side="right",padx=(4,0)); flat_button(trbar,self.t("jump_event"),self.jump_to_event).pack(side="right",padx=4); flat_button(trbar,self.t("blur_zones"),self.edit_blur_zones).pack(side="right",padx=4); flat_button(trbar,self.t("export"),self.open_export,accent=True).pack(side="right")

    def _build_right(self):
        hdr=tk.Frame(self.right,bg=PANEL); hdr.pack(fill="x",padx=12,pady=(12,6))
        tk.Label(hdr,text=self.t("telemetry").upper(),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",10)).pack(side="left")
        self.telemetry_badge=tk.Label(hdr,text="—",bg=CARD2,fg=MUTED,font=("Segoe UI Semibold",8),padx=7,pady=3); self.telemetry_badge.pack(side="right")
        speed_card=tk.Frame(self.right,bg=CARD,highlightthickness=1,highlightbackground=BORDER); speed_card.pack(fill="x",padx=10,pady=5)
        self.speed_value=tk.Label(speed_card,text="—",bg=CARD,fg="#ffffff",font=("Segoe UI Semibold",34)); self.speed_value.pack(side="left",padx=(12,4),pady=8)
        self.speed_unit=tk.Label(speed_card,text="MPH",bg=CARD,fg=MUTED,font=("Segoe UI Semibold",9)); self.speed_unit.pack(side="left",pady=(22,0))
        self.state_value=tk.Label(speed_card,text="—",bg=CARD,fg=MUTED,font=("Segoe UI Semibold",10)); self.state_value.pack(side="right",padx=12)
        grid=tk.Frame(self.right,bg=PANEL); grid.pack(fill="x",padx=8,pady=4); grid.grid_columnconfigure(0,weight=1,uniform="metric"); grid.grid_columnconfigure(1,weight=1,uniform="metric")
        self.metric_labels={}
        for i,(key,title) in enumerate((("gear",self.t("gear")),("steer",self.t("steering")),("accel",self.t("accelerator")),("brake",self.t("brake")))):
            c=tk.Frame(grid,bg=CARD,highlightthickness=1,highlightbackground=BORDER); c.grid(row=i//2,column=i%2,sticky="nsew",padx=3,pady=3)
            tk.Label(c,text=title.upper(),bg=CARD,fg=MUTED,font=("Segoe UI Semibold",7)).pack(anchor="w",padx=9,pady=(7,0))
            v=tk.Label(c,text="—",bg=CARD,fg=TEXT,font=("Segoe UI Semibold",13)); v.pack(anchor="w",padx=9,pady=(1,7)); self.metric_labels[key]=v
        tk.Label(self.right,text=self.t("route").upper(),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=12,pady=(8,4))
        self.route=RouteCanvas(self.right,self.language,self.settings.get("map_mode","Local Grid (offline)"),settings_dir()/"map_tiles"); self.route.pack(fill="x",padx=10)
        tk.Label(self.right,text=self.t("clip_insights").upper(),bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=12,pady=(10,4))
        self.insights=tk.Label(self.right,text=self.t("no_clip_selected"),justify="left",anchor="nw",bg=CARD,fg="#cbd5df",font=("Segoe UI",8),padx=10,pady=9,wraplength=270)
        self.insights.pack(fill="x",padx=10)
        self.event_info=tk.Label(self.right,text="",justify="left",anchor="nw",bg=PANEL,fg=MUTED,font=("Segoe UI",8),wraplength=270); self.event_info.pack(fill="x",padx=12,pady=8)
        rfoot=tk.Frame(self.right,bg=PANEL); rfoot.pack(side="bottom",fill="x",padx=10,pady=10)
        flat_button(rfoot,self.t("csv"),self.export_csv_ui).pack(side="left")
        flat_button(rfoot,self.t("shared_clips"),self.manage_shares).pack(side="right",padx=(4,0))
        flat_button(rfoot,self.t("share"),self.share_last).pack(side="right")

    def _build_bottom(self):
        foot=tk.Frame(self,bg=BG,height=30); foot.pack(fill="x",padx=12,pady=(0,8)); foot.pack_propagate(False)
        self.progress=ttk.Progressbar(foot,style="Dark.Horizontal.TProgressbar",mode="determinate",maximum=100,length=160); self.progress.pack(side="right",padx=(8,0),pady=8)
        tk.Label(foot,textvariable=self.status_var,bg=BG,fg=MUTED,font=("Segoe UI",8),anchor="w").pack(side="left",fill="x",expand=True)

    def _bind_shortcuts(self):
        keymap={"Space":"<space>","Left Arrow":"<Left>","Right Arrow":"<Right>","A":"<KeyPress-a>","D":"<KeyPress-d>","J":"<KeyPress-j>","L":"<KeyPress-l>","I":"<KeyPress-i>","O":"<KeyPress-o>","K":"<KeyPress-k>","E":"<KeyPress-e>","P":"<KeyPress-p>"}
        seek=int(self.settings.get("seek_seconds",10)); bindings=[(self.settings.get("shortcut_play","Space"),lambda _e:self.toggle_play()),(self.settings.get("shortcut_back","Left Arrow"),lambda _e:self.skip(-seek)),(self.settings.get("shortcut_forward","Right Arrow"),lambda _e:self.skip(seek)),(self.settings.get("shortcut_in","I"),lambda _e:self.set_in()),(self.settings.get("shortcut_out","O"),lambda _e:self.set_out())]
        for name,callback in bindings:
            seq=keymap.get(str(name))
            if seq:self.bind(seq,callback)
        self.bind("<Control-o>",lambda _e:self.browse_root());self.bind("<Control-e>",lambda _e:self.open_export());self.bind("<KeyPress-e>",lambda _e:self.jump_to_event());self.bind("<KeyPress-p>",lambda _e:self.save_snapshot())

    def _first_run_notice(self):
        messagebox.showinfo(APP_NAME,self.t("privacy_first_title")+"\n\n"+self.t("privacy_first_body"));self.settings["privacy_notice_seen"]=True;save_settings(self.settings)

    def browse_root(self):
        current=Path(self.root_path.get().strip()) if self.root_path.get().strip() else None
        initial=current if current and current.exists() else None
        if initial is None:
            roots=detect_teslacam_roots()
            if roots: initial=roots[0]
        if initial is None:
            videos=Path.home()/"Videos"
            initial=videos if videos.exists() else Path.home()
        p=filedialog.askdirectory(title=self.t("choose_teslacam"),initialdir=str(initial))
        if p:self.root_path.set(p);self.scan()

    def auto_detect_root(self,silent=False):
        roots=detect_teslacam_roots()
        if not roots:
            if not silent:messagebox.showinfo(APP_NAME,self.t("auto_detect_none"))
            return
        chosen=roots[0];self.root_path.set(str(chosen));self.status_var.set(self.tf("auto_detect_found",path=chosen));self.scan()

    def scan(self):
        p=Path(self.root_path.get().strip())
        if not p.exists():messagebox.showerror(APP_NAME,self.t("folder_not_exist"));return
        self.status_var.set(self.t("scanning"));self.progress["value"]=15;self.update_idletasks()
        try:self.groups=discover_clips(p)
        except Exception as exc:messagebox.showerror(APP_NAME,str(exc));return
        self.refresh_event_list();self.progress["value"]=0;self.status_var.set(self.tf("found_groups",count=len(self.groups)))
        children=self.event_tree.get_children()
        if children:
            first=children[0]; self.event_tree.selection_set(first); self.event_tree.focus(first); self.event_tree.see(first); self.on_event_select()

    def set_filter(self,kind):self.filter_kind=kind;self.refresh_event_list()
    def refresh_event_list(self):
        q=self.search_var.get().strip().lower();self.filtered_groups=[];self.event_tree.delete(*self.event_tree.get_children())
        for g in self.groups:
            if self.filter_kind!="All" and g.source_kind!=self.filter_kind:continue
            reason=(g.event_info or {}).get("reason") or (g.event_info or {}).get("event") or (g.event_info or {}).get("trigger") or "";trigger_label=event_reason_label(self.language,reason) if reason else "—";hay=f"{g.timestamp} {g.source_kind} {g.folder} {reason} {trigger_label}".lower()
            if q and q not in hay:continue
            self.filtered_groups.append(g);self.event_tree.insert("","end",iid=str(len(self.filtered_groups)-1),values=(g.display_time(),g.source_kind,trigger_label,len(g.cameras)))
        self.count_label.configure(text=str(len(self.filtered_groups)))
        for k,b in self.filter_buttons.items():b.configure(bg=ACCENT if k==self.filter_kind else CARD2)

    def on_event_select(self,_e=None):
        sel=self.event_tree.selection()
        if not sel:return
        idx=int(sel[0])
        if idx>=len(self.filtered_groups):return
        self.load_group(self.filtered_groups[idx])

    def _best_layout_for_group(self,g:ClipGroup):
        cams=set(g.cameras)
        if len(cams)<=1:return "Single Camera"
        if "left_pillar" in cams or "right_pillar" in cams or len(cams)>=5:return "Six Camera"
        return "Four Camera"

    def load_group(self,g:ClipGroup):
        self._load_token+=1;token=self._load_token;self.player.pause();self.selected_group=g;self.samples=[];self.telemetry_fps=36.0;self.video_duration=0.0;self.in_point=0.0;self.out_point=0.0;self.blur_zones=[];self.active_camera="front" if "front" in g.cameras else next(iter(g.cameras));self.triggered_camera=self._infer_triggered_camera(g.event_info);self.preview_layout.set(localized_choice(self.language,self._best_layout_for_group(g),LAYOUT_KEYS));self.clip_title.configure(text=f"{g.display_time()}   •   {g.source_kind}   •   {len(g.cameras)} cameras");self.telemetry_badge.configure(text=self.t("reading").upper(),fg=WARN);self.status_var.set(self.t("opening_sync"));self.route.set_empty_text(self.t("reading"));self.route.set_data([],36.0);self.insights.configure(text=self.t("reading"));self.event_info.configure(text="");self._update_telemetry_panel(0.0)
        try:self.player.load_group(g);self.video_duration=self.player.duration
        except Exception as exc: messagebox.showerror(APP_NAME,self.tf("could_not_open",error=exc)); return
        self.out_point=self.video_duration; self.timeline.set_data([],36.0,self.video_duration,self._event_relative_time(g)); self.timeline.set_trim(self.in_point,self.out_point)
        self.update_camera_layout(); self._update_tile_borders(); self.seek(0.0)
        def work():
            try:
                src=choose_telemetry_source(g); info=probe_video(src) if src else None; samples=load_telemetry(src) if src else []
                self._worker_q.put(("loaded",(token,g,samples,info)))
            except Exception as exc:self._worker_q.put(("error",(token,str(exc))))
        threading.Thread(target=work,daemon=True).start()

    def _poll_worker(self):
        try:
            while True:
                kind,payload=self._worker_q.get_nowait()
                if kind=="loaded":
                    token,g,samples,info=payload
                    if token!=self._load_token:continue
                    self.samples=samples; self.telemetry_fps=info.fps if info else 36.0
                    if info and info.duration>0:self.video_duration=info.duration; self.player.duration=info.duration
                    self.timeline.set_data(self.samples,self.telemetry_fps,self.video_duration,self._event_relative_time(g)); self.timeline.set_trim(self.in_point,self.out_point); self.route.set_empty_text(self.t("no_gps_route")); self.route.set_data(self.samples,self.telemetry_fps)
                    if samples:
                        self.telemetry_badge.configure(text=f"{len(samples)} {self.t('samples').upper()}",fg=GOOD); self.status_var.set(self.tf("telemetry_synced",count=len(samples),fps=self.telemetry_fps))
                    else:
                        self.telemetry_badge.configure(text=self.t("no_sei").upper(),fg=WARN); self.status_var.set(self.t("no_telemetry"))
                    self._update_insights(); self._update_event_info(); self.seek(self.player.position)
                elif kind=="error":
                    token,msg=payload
                    if token==self._load_token:self.telemetry_badge.configure(text=self.t("error").upper(),fg=DANGER); self.status_var.set(msg)
                elif kind=="export_progress":
                    frac,msg=payload; self.progress["value"]=frac*100; self.status_var.set(self.tf("exporting",percent=frac*100)); self._update_export_toast(frac,self.status_var.get())
                elif kind=="export_done":
                    output,encoder=payload; self.progress["value"]=0; self.last_output=Path(output); self.status_var.set(self.tf("export_complete",encoder=encoder,path=output)); self._finish_export_toast(True,self.status_var.get()); messagebox.showinfo(APP_NAME,self.tf("export_complete_dialog",path=output))
                elif kind=="export_error":
                    self.progress["value"]=0; self.status_var.set(self.t("export_failed")); self._finish_export_toast(False,self.t("export_failed")); messagebox.showerror(APP_NAME,str(payload))
        except queue.Empty: pass
        self.after(100,self._poll_worker)

    def _tick(self):
        if self.selected_group:
            pos=self.player.tick(); now=time.perf_counter()
            if self.player.playing and now-self._last_preview_update>=1/18:
                self._last_preview_update=now; self._refresh_frames(pos)
            self._update_position_ui(pos)
            if not self.player.playing and self.play_button.cget("text").startswith("⏸"):
                self.play_button.configure(text="▶  "+self.t("play"))
        self.after(35,self._tick)

    def _refresh_frames(self,pos=None):
        if not self.selected_group:return
        frames=self.player.get_frames(self.player.position if pos is None else pos); self.last_frames=frames
        for c,tile in self.tiles.items():
            if c not in self.selected_group.cameras: tile.set_placeholder(); continue
            frame=frames.get(c)
            if frame is None: continue
            width=max(120,tile.image.winfo_width()); height=max(90,tile.image.winfo_height()); tile.set_frame(frame,(width,height))

    def _update_position_ui(self,pos):
        self.time_label.configure(text=f"{fmt_time(pos)} / {fmt_time(self.video_duration)}"); self.timeline.set_position(pos); self.route.set_position(pos); self._update_telemetry_panel(pos)

    def toggle_play(self):
        if not self.selected_group:return
        playing=self.player.toggle(); self.play_button.configure(text=("⏸  "+self.t("pause")) if playing else ("▶  "+self.t("play")))
    def skip(self,seconds): self.player.skip(seconds); self._refresh_frames(); self._update_position_ui(self.player.position)
    def seek(self,seconds): self.player.seek(seconds); self._refresh_frames(); self._update_position_ui(self.player.position)
    def save_snapshot(self):
        if not self.selected_group:
            return
        self.player.pause()
        self._refresh_frames()
        frame = self.last_frames.get(self.active_camera)
        if frame is None:
            messagebox.showinfo(APP_NAME, self.t("no_frame"))
            return
        dest = filedialog.asksaveasfilename(
            title=self.t("save_snapshot"),
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg")],
            initialfile=f"{self.selected_group.timestamp}-{self.active_camera}-snapshot.png",
        )
        if not dest:
            return
        try:
            if not cv2.imwrite(dest, frame):
                raise RuntimeError("OpenCV could not write the image")
            self.status_var.set(self.tf("snapshot_saved", path=dest))
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def jump_to_event(self):
        if not self.selected_group:
            return
        pos = self._event_relative_time(self.selected_group)
        if pos is None:
            messagebox.showinfo(APP_NAME, self.t("no_event_marker"))
            return
        self.seek(pos)

    def set_in(self): self.in_point=self.player.position; self._normalize_trim();
    def set_out(self): self.out_point=self.player.position; self._normalize_trim();
    def clear_trim(self): self.in_point=0.0; self.out_point=self.video_duration; self._normalize_trim()
    def _normalize_trim(self):
        if self.out_point<=self.in_point: self.out_point=min(self.video_duration,self.in_point+0.1)
        self.timeline.set_trim(self.in_point,self.out_point); self.trim_label.configure(text=self.tf("trim_summary",start=fmt_time(self.in_point),end=fmt_time(self.out_point),seconds=self.out_point-self.in_point))

    def set_active_camera(self,camera):
        if self.selected_group and camera in self.selected_group.cameras:
            self.active_camera=camera; self._update_tile_borders();
            if canonical_choice(self.language, self.preview_layout.get(), LAYOUT_KEYS)=="Single Camera":self.update_camera_layout(); self._refresh_frames()
    def _update_tile_borders(self):
        for c,t in self.tiles.items(): t.set_active(c==self.active_camera,c==self.triggered_camera)

    def update_camera_layout(self):
        for t in self.tiles.values(): t.grid_forget()
        layout=canonical_choice(self.language, self.preview_layout.get(), LAYOUT_KEYS)
        if layout=="Single Camera":
            tile=self.tiles.get(self.active_camera,self.tiles["front"]); tile.grid(row=0,column=0,rowspan=2,columnspan=3,sticky="nsew",padx=1,pady=1)
            for i in range(3):self.wall.grid_columnconfigure(i,weight=1)
            for i in range(2):self.wall.grid_rowconfigure(i,weight=1)
        elif layout=="Four Camera":
            cams=[c for c in ("front","back","left_repeater","right_repeater")]
            for i,c in enumerate(cams): self.tiles[c].grid(row=i//2,column=i%2,sticky="nsew",padx=1,pady=1)
            for i in range(2):self.wall.grid_columnconfigure(i,weight=1); self.wall.grid_rowconfigure(i,weight=1)
            self.wall.grid_columnconfigure(2,weight=0)
        else:
            for i,c in enumerate(CAMERA_WALL_ORDER): self.tiles[c].grid(row=i//3,column=i%3,sticky="nsew",padx=1,pady=1)
            for i in range(3):self.wall.grid_columnconfigure(i,weight=1)
            for i in range(2):self.wall.grid_rowconfigure(i,weight=1)
        self.after(40,self._refresh_frames)

    def _sample_for_pos(self,pos):
        if not self.samples:return None
        idx=min(len(self.samples)-1,max(0,int(round(pos*self.telemetry_fps)))); return self.samples[idx]
    def _update_telemetry_panel(self,pos):
        s=self._sample_for_pos(pos)
        if not s:
            self.speed_value.configure(text="—"); self.speed_unit.configure(text="MPH" if self.settings.get("units","mph")=="mph" else "km/h"); self.state_value.configure(text="—",fg=MUTED)
            for label in self.metric_labels.values():label.configure(text="—",fg=TEXT)
            return
        mph=self.settings.get("units","mph")=="mph"; self.speed_value.configure(text=f"{s.speed_mph if mph else s.speed_kph:.0f}"); self.speed_unit.configure(text="MPH" if mph else "km/h")
        state=assist_label(self.language,s.autopilot_state); self.state_value.configure(text=state,fg=FSD if s.autopilot_state else MUTED)
        self.metric_labels["gear"].configure(text=s.gear); self.metric_labels["steer"].configure(text=f"{s.steering_wheel_angle:+.1f}°"); self.metric_labels["accel"].configure(text=f"{s.accelerator_pedal_position:.2f}"); self.metric_labels["brake"].configure(text=self.t("on") if s.brake_applied else self.t("off"),fg=DANGER if s.brake_applied else TEXT)

    def _update_insights(self):
        if not self.samples:self.insights.configure(text=self.t("no_telemetry_analytics")); return
        mph=self.settings.get("units","mph")=="mph"; speeds=[s.speed_mph if mph else s.speed_kph for s in self.samples]; unit="MPH" if mph else "km/h"; assist=sum(1 for s in self.samples if s.autopilot_state)/len(self.samples)*100
        dist_m=sum(max(0,s.vehicle_speed_mps) for s in self.samples)/max(self.telemetry_fps,1); dist=dist_m/1609.344 if mph else dist_m/1000; dunit="mi" if mph else "km"
        brakes=sum(1 for s in self.samples if s.brake_applied); text=f"{self.t('avg_speed')}   {sum(speeds)/len(speeds):.1f} {unit}\n{self.t('max_speed')}   {max(speeds):.1f} {unit}\n{self.t('driver_assist')}   {assist:.1f}%\n{self.t('distance_in_clip')}   {dist:.2f} {dunit}\n{self.t('brake_frames')}   {brakes}\n{self.t('telemetry_match')}   {len(self.samples)} {self.t('samples')}"
        self.insights.configure(text=text)

    def _update_event_info(self):
        g=self.selected_group
        if not g:return
        parts=[f"{self.t('source')}: {g.source_kind}",f"{self.t('folder')}: {g.folder.name}"]
        if g.event_info:
            reason=g.event_info.get("reason") or g.event_info.get("event") or g.event_info.get("trigger")
            if reason:parts.append(f"{self.t('trigger')}: {event_reason_label(self.language,reason)}")
            city=g.event_info.get("city"); street=g.event_info.get("street")
            if city or street:parts.append(self.t("location")+": "+", ".join(str(x) for x in (street,city) if x))
        if self.triggered_camera:parts.append(self.t("highlighted_camera")+": "+camera_label(self.language,self.triggered_camera))
        self.event_info.configure(text="\n".join(parts))

    def _infer_triggered_camera(self,info):
        if not info:return None
        blob=" ".join(str(v) for v in info.values()).lower()
        aliases={"front":["front"],"back":["rear","back"],"left_repeater":["left repeater","left_repeater"],"right_repeater":["right repeater","right_repeater"],"left_pillar":["left pillar","left_pillar"],"right_pillar":["right pillar","right_pillar"]}
        for cam,words in aliases.items():
            if any(w in blob for w in words):return cam
        return None

    def _event_relative_time(self,g):
        if not g.event_info:return None
        value=g.event_info.get("timestamp") or g.event_info.get("time")
        if not value:return None
        try:
            base=datetime.strptime(g.timestamp,"%Y-%m-%d_%H-%M-%S")
            txt=str(value).replace("Z","+00:00"); dt=datetime.fromisoformat(txt)
            if dt.tzinfo:dt=dt.replace(tzinfo=None)
            rel=(dt-base).total_seconds(); return rel if 0<=rel<=120 else None
        except Exception:return None

    def delete_selected(self):
        g=self.selected_group
        if not g:return
        if not messagebox.askyesno(APP_NAME,self.tf("delete_confirm",time=g.display_time(),count=len(g.cameras))):return
        try:
            try:
                from send2trash import send2trash
                for p in g.cameras.values(): send2trash(str(p))
            except Exception:
                for p in g.cameras.values(): p.unlink(missing_ok=True)
            self.player.release(); self.selected_group=None; self.scan()
        except Exception as exc:messagebox.showerror(APP_NAME,str(exc))

    def export_csv_ui(self):
        if not self.selected_group or not self.samples:return
        dest=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],initialfile=f"{self.selected_group.timestamp}-telemetry.csv")
        if dest:
            try:export_csv(self.samples,Path(dest),self.telemetry_fps); self.status_var.set(self.tf("csv_exported",path=dest))
            except Exception as exc:messagebox.showerror(APP_NAME,str(exc))

    def _compose_preview_image(self,layout=None):
        layout=canonical_choice(self.language, layout or self.preview_layout.get(), LAYOUT_KEYS); frames=self.last_frames or self.player.get_frames(self.player.position)
        if layout=="Single Camera":cams=[self.active_camera]; cols,rows=1,1; size=(1280,720)
        elif layout=="Four Camera":cams=[c for c in ("front","back","left_repeater","right_repeater")]; cols,rows=2,2; size=(1280,720)
        else:cams=list(CAMERA_WALL_ORDER); cols,rows=3,2; size=(1440,810)
        tw,th=size[0]//cols,size[1]//rows; canvas=Image.new("RGB",size,(3,5,6))
        for i,c in enumerate(cams):
            frame=frames.get(c)
            if frame is None:continue
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); img=Image.fromarray(rgb); img.thumbnail((tw,th),Image.Resampling.LANCZOS); x=(i%cols)*tw+(tw-img.width)//2; y=(i//cols)*th+(th-img.height)//2; canvas.paste(img,(x,y))
        return canvas

    def edit_blur_zones(self):
        if not self.selected_group:return
        self.player.pause(); self._refresh_frames(); image=self._compose_preview_image(canonical_choice(self.language, self.preview_layout.get(), LAYOUT_KEYS)); dlg=BlurZoneDialog(self,image,self.blur_zones,int(self.settings.get("glass_blur",12)),self.language); self.wait_window(dlg)
        if dlg.result is not None:self.blur_zones=dlg.result; self.status_var.set(self.tf("privacy_blur_count",count=len(self.blur_zones)))

    def open_export(self):
        if not self.selected_group:return
        d=tk.Toplevel(self); d.title(self.t("export_clip")); d.geometry("470x635"); d.configure(bg=BG); d.transient(self); d.grab_set()
        tk.Label(d,text=self.t("export_clip").upper(),bg=BG,fg=TEXT,font=("Segoe UI Semibold",14)).pack(anchor="w",padx=18,pady=(16,2)); tk.Label(d,text=f"{fmt_time(self.in_point)} → {fmt_time(self.out_point)}  •  {self.out_point-self.in_point:.1f}s",bg=BG,fg=MUTED,font=("Segoe UI",9)).pack(anchor="w",padx=18,pady=(0,12))
        form=tk.Frame(d,bg=PANEL,highlightthickness=1,highlightbackground=BORDER); form.pack(fill="both",expand=True,padx=18,pady=4)
        preview_canonical=canonical_choice(self.language,self.preview_layout.get(),LAYOUT_KEYS)
        layout=tk.StringVar(value=localized_choice(self.language,self.settings.get("export_layout",preview_canonical),LAYOUT_KEYS)); quality=tk.StringVar(value=localized_choice(self.language,self.settings.get("export_quality","High"),QUALITY_KEYS)); encoder=tk.StringVar(value=self.t("auto") if self.settings.get("encoder","Auto")=="Auto" else self.settings.get("encoder","Auto")); dash=tk.StringVar(value=localized_choice(self.language,self.settings.get("dashboard_size","Medium"),DASHBOARD_SIZE_KEYS)); dashstyle=tk.StringVar(value=localized_choice(self.language,self.settings.get("dashboard_style","Default"),DASHBOARD_STYLE_KEYS)); stamp=tk.BooleanVar(value=self.settings.get("show_timestamp",True)); minimap=tk.BooleanVar(value=self.settings.get("show_minimap",False)); gps=tk.BooleanVar(value=self.settings.get("show_gps_text",False))
        def row(label,var,values):
            r=tk.Frame(form,bg=PANEL); r.pack(fill="x",padx=12,pady=7); tk.Label(r,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",9),width=18,anchor="w").pack(side="left"); cb=ttk.Combobox(r,textvariable=var,values=values,state="readonly",style="Dark.TCombobox"); cb.pack(side="right",fill="x",expand=True)
        row(self.t("layout"),layout,tuple(localized_choice(self.language,c,LAYOUT_KEYS) for c in LAYOUT_KEYS)); row(self.t("quality"),quality,tuple(localized_choice(self.language,c,QUALITY_KEYS) for c in QUALITY_KEYS)); row(self.t("encoder"),encoder,[self.t("auto")]+available_encoders()); row(self.t("dashboard_style"),dashstyle,tuple(localized_choice(self.language,c,DASHBOARD_STYLE_KEYS) for c in DASHBOARD_STYLE_KEYS)); row(self.t("dashboard_size"),dash,tuple(localized_choice(self.language,c,DASHBOARD_SIZE_KEYS) for c in DASHBOARD_SIZE_KEYS))
        for label,var in ((self.t("timestamp"),stamp),(self.t("minimap"),minimap),(self.t("gps_text"),gps)):
            r=tk.Frame(form,bg=PANEL); r.pack(fill="x",padx=12,pady=6); tk.Label(r,text=label,bg=PANEL,fg=TEXT,font=("Segoe UI",9)).pack(side="left"); tk.Checkbutton(r,variable=var,bg=PANEL,activebackground=PANEL,selectcolor=CARD2).pack(side="right")
        tk.Label(form,text=self.tf("privacy_blur_count",count=len(self.blur_zones))+"\n"+self.t("gps_minimap_local"),bg=PANEL,fg=MUTED,justify="left",font=("Segoe UI",8)).pack(anchor="w",padx=12,pady=8)
        buttons=tk.Frame(d,bg=BG); buttons.pack(fill="x",padx=18,pady=14)
        flat_button(buttons,self.t("cancel"),d.destroy).pack(side="right",padx=4)
        def go():
            dest=filedialog.asksaveasfilename(parent=d,defaultextension=".mp4",filetypes=[("MP4 video","*.mp4")],initialfile=f"{self.selected_group.timestamp}-export.mp4")
            if not dest:return
            layout_value=canonical_choice(self.language,layout.get(),LAYOUT_KEYS); quality_value=canonical_choice(self.language,quality.get(),QUALITY_KEYS); encoder_value="Auto" if encoder.get() in ("Auto",self.t("auto")) else encoder.get(); dash_value=canonical_choice(self.language,dash.get(),DASHBOARD_SIZE_KEYS); dashstyle_value=canonical_choice(self.language,dashstyle.get(),DASHBOARD_STYLE_KEYS)
            self.settings.update({"export_layout":layout_value,"export_quality":quality_value,"encoder":encoder_value,"dashboard_size":dash_value,"dashboard_style":dashstyle_value,"show_timestamp":stamp.get(),"show_minimap":minimap.get(),"show_gps_text":gps.get()}); save_settings(self.settings); d.destroy()
            opt=ExportOptions(layout=layout_value,active_camera=self.active_camera,start=self.in_point,end=self.out_point,units=self.settings.get("units","mph"),language=self.language,encoder=encoder_value,quality=quality_value,dashboard_size=dash_value,dashboard_style=dashstyle_value,show_timestamp=stamp.get(),timestamp_format=({"YYYY-MM-DD":"%Y-%m-%d","MM/DD/YYYY":"%m/%d/%Y","DD/MM/YYYY":"%d/%m/%Y","DD Mon YYYY":"%d %b %Y"}.get(self.settings.get("date_format","YYYY-MM-DD"),"%Y-%m-%d") + (" %H:%M:%S" if self.settings.get("time_format")=="24h" else " %I:%M:%S %p")),show_minimap=minimap.get(),show_gps_text=gps.get(),blur_zones=list(self.blur_zones))
            self.start_export(Path(dest),opt)
        flat_button(buttons,self.t("export_mp4"),go,accent=True).pack(side="right",padx=4)

    def _show_export_toast(self):
        try:
            if self.export_toast and self.export_toast.winfo_exists(): self.export_toast.destroy()
        except Exception: pass
        d=tk.Toplevel(self); d.title(self.t("export_clip")); d.geometry("390x120"); d.configure(bg=BG); d.transient(self); d.resizable(False,False); self.export_toast=d
        self.export_toast_label=tk.Label(d,text=self.t("preparing_export"),bg=BG,fg=TEXT,font=("Segoe UI",9),anchor="w"); self.export_toast_label.pack(fill="x",padx=14,pady=(14,6))
        self.export_toast_progress=ttk.Progressbar(d,style="Dark.Horizontal.TProgressbar",mode="determinate",maximum=100); self.export_toast_progress.pack(fill="x",padx=14,pady=4); flat_button(d,self.t("close"),d.withdraw).pack(side="right",padx=14,pady=8)

    def _update_export_toast(self,frac,text):
        try:
            if self.export_toast and self.export_toast.winfo_exists():
                if self.export_toast_progress is not None:self.export_toast_progress["value"]=max(0,min(100,frac*100))
                if self.export_toast_label is not None:self.export_toast_label.configure(text=text)
        except Exception:pass
    def _finish_export_toast(self,success,text):
        self._update_export_toast(1.0 if success else 0.0,text)
        try:
            if self.export_toast and self.export_toast.winfo_exists():self.export_toast.deiconify();self.export_toast.lift()
        except Exception:pass

    def start_export(self,dest,opt):
        g=self.selected_group;samples=list(self.samples);fps=self.telemetry_fps
        if not g:return
        self.progress["value"]=1;self.status_var.set(self.t("preparing_export"));self._show_export_toast()
        def work():
            try:
                enc=export_video(g,samples,fps,dest,opt,lambda p,m:self._worker_q.put(("export_progress",(p,m))));self._worker_q.put(("export_done",(dest,enc)))
            except Exception as exc:self._worker_q.put(("export_error",str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def _shares_path(self):return settings_dir()/"shares.json"
    def _load_shares(self):
        try:
            data=json.loads(self._shares_path().read_text(encoding="utf-8"))
            if isinstance(data,list):
                now=time.time();return [x for x in data if float(x.get("expires_at",now+1))>now-86400]
        except Exception:pass
        return []
    def _save_shares(self,items):
        p=self._shares_path();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(items,indent=2),encoding="utf-8")

    def manage_shares(self):
        d=tk.Toplevel(self);d.title(self.t("shared_clips"));d.geometry("760x430");d.configure(bg=BG);d.transient(self)
        tk.Label(d,text=self.t("shared_clips").upper(),bg=BG,fg=TEXT,font=("Segoe UI Semibold",14)).pack(anchor="w",padx=16,pady=(16,3));tk.Label(d,text=self.t("shared_clips_help"),bg=BG,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",padx=16,pady=(0,10))
        tree=ttk.Treeview(d,columns=("file","created","expires","url"),show="headings",style="Dark.Treeview",selectmode="browse")
        for c,t,w in (("file",self.t("file").upper(),170),("created",self.t("created").upper(),125),("expires",self.t("expires").upper(),125),("url","URL",300)):tree.heading(c,text=t);tree.column(c,width=w,anchor="w")
        tree.pack(fill="both",expand=True,padx=16,pady=4);items=self._load_shares()
        for i,it in enumerate(items):
            def dt(v):
                try:return datetime.fromtimestamp(float(v)).strftime("%Y-%m-%d %H:%M")
                except:return "—"
            tree.insert("","end",iid=str(i),values=(it.get("file",""),dt(it.get("created",0)),dt(it.get("expires_at",0)),it.get("url","")))
        bar=tk.Frame(d,bg=BG);bar.pack(fill="x",padx=16,pady=12)
        def selected():
            sel=tree.selection();return (int(sel[0]),items[int(sel[0])]) if sel else (None,None)
        def copy():
            _,it=selected()
            if it:self.clipboard_clear();self.clipboard_append(it.get("url",""))
        def open_url():
            _,it=selected()
            if it:webbrowser.open(it.get("url",""))
        def remove():
            idx,it=selected()
            if it is None:return
            if messagebox.askyesno(APP_NAME,self.t("remove_history_confirm"),parent=d):items.pop(idx);self._save_shares(items);d.destroy();self.manage_shares()
        def remote_delete():
            idx,it=selected()
            if it is None:return
            delete_url=it.get("delete_url")
            if not delete_url:messagebox.showinfo(APP_NAME,self.t("no_delete_url"),parent=d);return
            if not messagebox.askyesno(APP_NAME,self.t("delete_remote_confirm"),parent=d):return
            try:
                req=urllib.request.Request(delete_url,method="DELETE");urllib.request.urlopen(req,timeout=15).read();items.pop(idx);self._save_shares(items);d.destroy();self.manage_shares()
            except Exception as exc:messagebox.showerror(APP_NAME,str(exc),parent=d)
        def preview():
            _,it=selected()
            if not it:return
            local=Path(str(it.get("local_path") or ""))
            if local.exists():
                try:os.startfile(str(local)) if os.name=="nt" else webbrowser.open(local.as_uri())
                except Exception:webbrowser.open(it.get("url",""))
            elif it.get("url"):webbrowser.open(it.get("url",""))
        flat_button(bar,self.t("preview"),preview).pack(side="left",padx=3);flat_button(bar,self.t("copy_link"),copy).pack(side="left",padx=3);flat_button(bar,self.t("open"),open_url).pack(side="left",padx=3);flat_button(bar,self.t("delete_remote"),remote_delete,danger=True).pack(side="left",padx=3);flat_button(bar,self.t("remove_history"),remove).pack(side="left",padx=3);flat_button(bar,self.t("close"),d.destroy,accent=True).pack(side="right")

    def share_last(self):
        if not self.last_output or not self.last_output.exists():messagebox.showinfo(APP_NAME,self.t("share_first"));return
        endpoint=str(self.settings.get("share_endpoint","")).strip()
        if not endpoint:messagebox.showinfo(APP_NAME,self.t("no_share_endpoint"));return
        if not messagebox.askyesno(APP_NAME,self.t("share_confirm")):return
        self.status_var.set(self.t("uploading"));threading.Thread(target=self._share_worker,args=(self.last_output,endpoint),daemon=True).start()
    def _share_worker(self,path,endpoint):
        try:
            boundary="----TTS"+str(int(time.time()*1000));data=path.read_bytes();head=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: video/mp4\r\n\r\n").encode();body=head+data+f"\r\n--{boundary}--\r\n".encode();req=urllib.request.Request(endpoint,data=body,headers={"Content-Type":f"multipart/form-data; boundary={boundary}"},method="POST")
            with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode("utf-8","replace")
            try:
                payload=json.loads(text)
                if not isinstance(payload,dict):payload={"url":str(payload)}
            except Exception:payload={"url":text.strip()}
            self.after(0,lambda p=payload:self._share_done(p))
        except Exception as exc:self.after(0,lambda:messagebox.showerror(APP_NAME,self.tf("share_failed",error=exc)))
    def _share_done(self,payload):
        url=str(payload.get("url") or payload.get("link") or "").strip()
        if not url:messagebox.showerror(APP_NAME,self.t("no_share_url"));return
        item={"file":self.last_output.name if self.last_output else "clip.mp4","local_path":str(self.last_output) if self.last_output else "","url":url,"delete_url":payload.get("delete_url",""),"created":time.time(),"expires_at":float(payload.get("expires_at") or (time.time()+48*3600))};shares=self._load_shares();shares.insert(0,item);self._save_shares(shares[:100]);self.clipboard_clear();self.clipboard_append(url);self.status_var.set(self.t("share_copied"));messagebox.showinfo(APP_NAME,self.tf("share_copied_dialog",url=url))

    def open_settings(self):
        d=tk.Toplevel(self);d.title(self.t("settings_title"));d.geometry("640x790");d.configure(bg=BG);d.transient(self);d.grab_set();tk.Label(d,text=self.t("settings_title").upper(),bg=BG,fg=TEXT,font=("Segoe UI Semibold",14)).pack(anchor="w",padx=18,pady=(16,10));scroller=tk.Frame(d,bg=BG);scroller.pack(fill="both",expand=True,padx=18,pady=(0,10));canvas=tk.Canvas(scroller,bg=PANEL,highlightthickness=1,highlightbackground=BORDER);scrollbar=ttk.Scrollbar(scroller,orient="vertical",command=canvas.yview);canvas.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side="right",fill="y");canvas.pack(side="left",fill="both",expand=True);box=tk.Frame(canvas,bg=PANEL);window=canvas.create_window((0,0),window=box,anchor="nw");box.bind("<Configure>",lambda _e:canvas.configure(scrollregion=canvas.bbox("all")));canvas.bind("<Configure>",lambda e:canvas.itemconfigure(window,width=e.width));d.bind("<MouseWheel>",lambda e:canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        units=tk.StringVar(value=self.settings.get("units","mph"));timefmt=tk.StringVar(value=self.settings.get("time_format","12h"));datefmt=tk.StringVar(value=self.settings.get("date_format","YYYY-MM-DD"));mapmode=tk.StringVar(value=localized_choice(self.language,self.settings.get("map_mode","Local Grid (offline)"),MAP_MODE_KEYS));lang=tk.StringVar(value=self.language);seek=tk.StringVar(value=str(self.settings.get("seek_seconds",10)));default=tk.StringVar(value=self.settings.get("default_folder",""));repo=tk.StringVar(value=self.settings.get("update_repo",""));support=tk.StringVar(value=self.settings.get("support_url",""));support_ep=tk.StringVar(value=self.settings.get("support_endpoint",""));share=tk.StringVar(value=self.settings.get("share_endpoint",""));blur=tk.StringVar(value=str(self.settings.get("glass_blur",12)));updates=tk.BooleanVar(value=self.settings.get("check_updates",True));sp=tk.StringVar(value=self.settings.get("shortcut_play","Space"));sb=tk.StringVar(value=self.settings.get("shortcut_back","Left Arrow"));sf=tk.StringVar(value=self.settings.get("shortcut_forward","Right Arrow"));si=tk.StringVar(value=self.settings.get("shortcut_in","I"));so=tk.StringVar(value=self.settings.get("shortcut_out","O"))
        def field(label,var,values=None):
            r=tk.Frame(box,bg=PANEL);r.pack(fill="x",padx=12,pady=7);tk.Label(r,text=label,bg=PANEL,fg=MUTED,font=("Segoe UI",9),width=18,anchor="w").pack(side="left")
            if values:w=ttk.Combobox(r,textvariable=var,values=values,state="readonly",style="Dark.TCombobox")
            else:w=tk.Entry(r,textvariable=var,bg=CARD2,fg=TEXT,insertbackground="white",relief="flat")
            w.pack(side="right",fill="x",expand=True,ipady=4)
        field(self.t("units"),units,("mph","km/h"));field(self.t("time_format"),timefmt,("12h","24h"));field(self.t("date_format"),datefmt,("YYYY-MM-DD","MM/DD/YYYY","DD/MM/YYYY","DD Mon YYYY"));field(self.t("map_mode"),mapmode,tuple(localized_choice(self.language,c,MAP_MODE_KEYS) for c in MAP_MODE_KEYS));field(self.t("language"),lang,LANGUAGES);field(self.t("seek_seconds"),seek);field(self.t("default_folder"),default);field(self.t("github_update_repo"),repo);field(self.t("support_url"),support);field(self.t("support_chat_endpoint"),support_ep);field(self.t("sharing_endpoint"),share);field(self.t("blur_strength"),blur)
        keys=("Space","Left Arrow","Right Arrow","A","D","J","K","L","I","O");field(self.t("play_pause_key"),sp,keys);field(self.t("seek_back_key"),sb,keys);field(self.t("seek_forward_key"),sf,keys);field(self.t("set_in_key"),si,keys);field(self.t("set_out_key"),so,keys)
        rr=tk.Frame(box,bg=PANEL);rr.pack(fill="x",padx=12,pady=7);tk.Label(rr,text=self.t("check_updates"),bg=PANEL,fg=TEXT,font=("Segoe UI",9)).pack(side="left");tk.Checkbutton(rr,variable=updates,bg=PANEL,activebackground=PANEL,selectcolor=CARD2).pack(side="right");tk.Label(box,text=self.t("settings_hint"),bg=PANEL,fg=MUTED,wraplength=520,justify="left",font=("Segoe UI",8)).pack(anchor="w",padx=12,pady=(10,4));tk.Label(box,text=self.t("map_privacy_note"),bg=PANEL,fg=MUTED,wraplength=520,justify="left",font=("Segoe UI",8)).pack(anchor="w",padx=12,pady=(0,10));buttons=tk.Frame(d,bg=BG);buttons.pack(fill="x",padx=18,pady=(0,16));flat_button(buttons,self.t("cancel"),d.destroy).pack(side="right",padx=4)
        def save():
            try:seekn=max(1,int(seek.get()))
            except:seekn=10
            self.settings.update({"units":units.get(),"time_format":timefmt.get(),"date_format":datefmt.get(),"map_mode":canonical_choice(self.language,mapmode.get(),MAP_MODE_KEYS),"language":lang.get(),"seek_seconds":seekn,"default_folder":default.get(),"update_repo":repo.get().strip(),"support_url":support.get().strip(),"support_endpoint":support_ep.get().strip(),"share_endpoint":share.get().strip(),"glass_blur":max(2,min(40,int(blur.get() or 12))),"check_updates":updates.get(),"shortcut_play":sp.get(),"shortcut_back":sb.get(),"shortcut_forward":sf.get(),"shortcut_in":si.get(),"shortcut_out":so.get()});save_settings(self.settings);self.language=lang.get();d.destroy();self._update_insights();messagebox.showinfo(APP_NAME,self.t("settings_saved"))
        flat_button(buttons,self.t("save"),save,accent=True).pack(side="right",padx=4)

    def open_support(self):
        d=tk.Toplevel(self);d.title(self.t("support_about"));d.geometry("620x590");d.configure(bg=BG);d.transient(self);tk.Label(d,text=f"{APP_NAME} {APP_VERSION}",bg=BG,fg=TEXT,font=("Segoe UI Semibold",15)).pack(anchor="w",padx=18,pady=(18,4));tk.Label(d,text=self.t("unofficial_notice"),bg=BG,fg=MUTED,font=("Segoe UI",9)).pack(anchor="w",padx=18);msg=self.t("local_first_help");tk.Label(d,text=msg,bg=PANEL,fg="#d7e0e8",justify="left",wraplength=560,padx=14,pady=12,font=("Segoe UI",9)).pack(fill="x",padx=18,pady=12);tk.Label(d,text=self.t("support_feedback").upper(),bg=BG,fg=TEXT,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=18,pady=(2,4));transcript=tk.Text(d,height=12,bg="#0c1218",fg="#dce6ef",insertbackground="white",relief="flat",wrap="word",font=("Segoe UI",9),state="disabled");transcript.pack(fill="both",expand=True,padx=18,pady=(0,6))
        def add_line(who,text):transcript.configure(state="normal");transcript.insert("end",f"{who}: {text}\n\n");transcript.see("end");transcript.configure(state="disabled")
        endpoint=str(self.settings.get("support_endpoint","")).strip();add_line(self.t("studio"),self.t("support_configured") if endpoint else self.t("support_not_configured"));entryrow=tk.Frame(d,bg=BG);entryrow.pack(fill="x",padx=18,pady=4);message=tk.StringVar();ent=tk.Entry(entryrow,textvariable=message,bg=CARD2,fg=TEXT,insertbackground="white",relief="flat",font=("Segoe UI",9));ent.pack(side="left",fill="x",expand=True,ipady=7)
        def send():
            text=message.get().strip();ep=str(self.settings.get("support_endpoint","")).strip()
            if not text:return
            if not ep:messagebox.showinfo(APP_NAME,self.t("configure_support_endpoint"),parent=d);return
            message.set("");add_line(self.t("you"),text);add_line(self.t("studio"),self.t("sending"))
            def work():
                try:
                    payload=json.dumps({"message":text,"version":APP_VERSION,"platform":sys.platform}).encode("utf-8");req=urllib.request.Request(ep,data=payload,headers={"Content-Type":"application/json","User-Agent":APP_NAME},method="POST")
                    with urllib.request.urlopen(req,timeout=20) as r:raw=r.read().decode("utf-8","replace")
                    try: data=json.loads(raw); reply=data.get("reply") or data.get("message") or raw
                    except Exception: reply=raw
                    self.after(0,lambda:add_line(self.t("support_name"),str(reply)))
                except Exception as exc:self.after(0,lambda:add_line(self.t("studio"),self.tf("send_failed",error=exc)))
            threading.Thread(target=work,daemon=True).start()
        flat_button(entryrow,self.t("send"),send,accent=True).pack(side="right",padx=(6,0)); ent.bind("<Return>",lambda _e:send())
        bar=tk.Frame(d,bg=BG); bar.pack(fill="x",padx=18,pady=(8,16))
        def support():
            u=self.settings.get("support_url","")
            if u:webbrowser.open(u)
            else:messagebox.showinfo(APP_NAME,self.t("configure_support_url"),parent=d)
        flat_button(bar,self.t("open_support_page"),support).pack(side="left"); flat_button(bar,self.t("check_updates"),lambda:self.check_updates(True)).pack(side="left",padx=6); flat_button(bar,self.t("shared_clips"),self.manage_shares).pack(side="left",padx=6); flat_button(bar,self.t("close"),d.destroy,accent=True).pack(side="right")

    def check_updates(self,manual=True):
        repo=str(self.settings.get("update_repo","")).strip()
        if not repo:
            if manual:messagebox.showinfo(APP_NAME,self.t("set_github_repo"))
            return
        def work():
            try:
                req=urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",headers={"User-Agent":APP_NAME})
                with urllib.request.urlopen(req,timeout=12) as r:data=json.load(r)
                tag=str(data.get("tag_name","")).lstrip("v"); assets=data.get("assets") or []
                asset=self._select_update_asset(assets)
                self.after(0,lambda:self._update_result(tag,asset,data.get("html_url"),manual))
            except Exception as exc:
                if manual:self.after(0,lambda:messagebox.showerror(APP_NAME,self.tf("update_check_failed",error=exc)))
        threading.Thread(target=work,daemon=True).start()
    def _select_update_asset(self, assets):
        def name(a):
            return str(a.get("name", "")).lower()
        if os.name == "nt":
            return next((a for a in assets if name(a).endswith(".exe") and "setup" in name(a)), None)
        if sys.platform == "darwin":
            machine = platform.machine().lower()
            preferred = ("arm64", "apple-silicon") if machine in ("arm64", "aarch64") else ("x86_64", "intel")
            dmg_assets = [a for a in assets if name(a).endswith(".dmg")]
            return next((a for a in dmg_assets if any(token in name(a) for token in preferred)), dmg_assets[0] if dmg_assets else None)
        return None

    def _update_result(self,tag,asset,page,manual):
        def ver(v):
            try:return tuple(int(x) for x in str(v).split(".")[:3])
            except:return (0,)
        if not tag or ver(tag)<=ver(APP_VERSION):
            if manual:messagebox.showinfo(APP_NAME,self.tf("up_to_date",version=APP_VERSION))
            return
        if asset and messagebox.askyesno(APP_NAME,self.tf("version_available",version=tag)):
            url=asset.get("browser_download_url"); name=asset.get("name") or "Cammetry-Setup.exe"; dest=Path(tempfile.gettempdir())/name
            def dl():
                try:urllib.request.urlretrieve(url,dest); self.after(0,lambda:self._launch_installer(dest))
                except Exception as exc:self.after(0,lambda:messagebox.showerror(APP_NAME,str(exc)))
            threading.Thread(target=dl,daemon=True).start()
        elif page:webbrowser.open(page)
    def _launch_installer(self,path):
        try:
            if os.name == "nt":
                os.startfile(str(path))
                self.after(500,self.destroy)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                webbrowser.open(path.as_uri())
        except Exception as exc:messagebox.showerror(APP_NAME,str(exc))
