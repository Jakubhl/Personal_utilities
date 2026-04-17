import customtkinter
from tkinter import font as tkFont
import json
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import uuid

app_name="Calendar Manager"
app_version="1.0.0"
customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("dark-blue")
root=customtkinter.CTk(fg_color="#212121")
root.geometry("1200x900")
root.title(f"{app_name} v_{app_version}")
# root.wm_iconbitmap(app_icon)
root.update_idletasks()

class Tools:
    @classmethod    
    def calc_days_in_month(cls,current_month):
        months_30days = [4,6,9,11]
        if current_month == 2:
            days_in_month = 28
        elif current_month in months_30days:
            days_in_month = 30
        else:
            days_in_month = 31
            
        return days_in_month
    
    @classmethod
    def get_day_of_week(cls,year, month, day):
        day_of_week = date(year, month, day).weekday()# 0=pondělí ... 6=neděle
        return day_of_week

    @classmethod
    def make_wrapping(cls,text):
        # text = re.sub(r'\n{3,}', '\n', str(text)) # odstraní více jak tři mezery za sebou
        lines = text.split("\n")
        whole_new_string = ""
        number_of_chars = 0
        max_num_of_chars_one_line = 35

        fitted_lines = []
        for line in lines:
            line = line.rstrip()
            if len(line) > max_num_of_chars_one_line:
                text_splitted = line.split(" ")
                # text_splitted = [x for x in text_splitted if x]
                new_string = ""
                for items in text_splitted:
                    number_of_chars += len(items)
                    if number_of_chars > max_num_of_chars_one_line:
                        if new_string == "": # osetreni odsazeni na prvnim radku
                            new_string += str(items) + " "
                            number_of_chars = len(items)
                        else:
                            new_string += "\n" + str(items) + " "
                            number_of_chars = len(items)
                    else: 
                        new_string += str(items) + " "

                fitted_lines.append(new_string + "\n")
            else:
                if line == "":
                    fitted_lines.append("\n")
                else:
                    fitted_lines.append(line+"\n")

        for items in fitted_lines:
            whole_new_string += items

        if whole_new_string.endswith("\n"):
            whole_new_string = whole_new_string.rstrip("\n")

        return whole_new_string
    

class FakeContextMenu(customtkinter.CTkScrollableFrame):
    def __init__(self, parent, values, values2=[], mirror = False, command=None, del_option = False, del_cmd = None,selected_day = 1, **kwargs):
        super().__init__(parent, **kwargs)
        self.command = command
        self.parent = parent
        self.del_cmd = del_cmd
        self.del_option = del_option
        self.buttons = []
        self.one_button_height = 50
        self.selected_day = selected_day
        width = kwargs.get("width")
        self._scrollbar.configure(width=15)
        self._scrollbar.configure(corner_radius=10)
        
        note_index = 0
        for val in values:
            btn = customtkinter.CTkButton(self, text=str(val["type"]), font=("Arial", 20), fg_color="transparent", hover_color="gray25",
                                command=lambda v=val: self.on_select(v))
            btn.pack(fill="x", pady=2,expand=True)
            self.one_button_height = btn._current_height
            self.buttons.append(btn)
            try:
                wrapped_text = Tools.make_wrapping(values2[note_index])
                if mirror:
                    ToolTip(btn," "+wrapped_text+" ",parent.master,subwindow_status=True,in_listbox=True,reverse=True,listbox_width=width-50)
                else:
                    ToolTip(btn," "+wrapped_text+" ",parent.master,subwindow_status=True,in_listbox=True)
            except Exception as eee:
                pass
            note_index +=1


    def on_select(self, value):
        if self.command:
            print("selected",value)
            self.parent.master.after(100, lambda: self.command(value,self.selected_day))
    def deletion(self, value):
        if self.del_cmd:
            # self.del_cmd(value)
            self.parent.master.after(100, lambda: self.del_cmd(value))

class ToolTip:
    def __init__(self, widget, text, root,unbind=False,subwindow_status=False,reverse=False,in_listbox=False,listbox_width=0):
        self.widget = widget
        self.text = text
        self.root = root
        self.tip_window = None
        self.listbox_width = listbox_width
        self.in_listbox = in_listbox
        self.subwindow_status = subwindow_status
        self.reverse = reverse
        if unbind:
            self.unbind_all("",self.widget)
        else:
            self.bind_it()

    def bind_it(self):
        self.widget.bind("<Enter>",lambda e,widget = self.widget: self.really_entering(e,widget))
        self.widget.bind("<Leave>",lambda e,widget = self.widget: self.really_leaving(e,widget))
        self.widget.bind("<Button-1>",lambda e,widget = self.widget:self.just_destroy(e,widget))

    def unbind_all(self,e,widget):
        try:
            self.tip_window.update_idletasks()
            # print("destroying")
            self.tip_window.destroy()
            self.root.after(0,self.tip_window.destroy)
        except Exception as ee:
            pass
        widget.unbind("<Enter>")
        widget.unbind("<Leave>")
        widget.unbind("<Button-1>")

    def just_destroy(self,e,widget,unbind=True):
        # if self.tip_window:
        try:
            self.tip_window.update_idletasks()
        except Exception:
            pass
        try:
            self.tip_window.destroy()
            # self.root.after(0,self.tip_window.destroy)
        except Exception as ee:
            # print(ee)
            pass
        self.tip_window = None
        
    def really_entering(self,e,widget):
        if self.tip_window != None:
            return

        def show_tooltip_v2(e):
            screen_x = self.root.winfo_pointerx()
            screen_y = self.root.winfo_pointery()
            parent_x = self.root.winfo_rootx()+e.x
            parent_y = self.root.winfo_rooty()+e.y
            local_x = screen_x - parent_x +self.widget.winfo_width()
            local_y = screen_y - parent_y +self.widget.winfo_height()
            self.tip_window = customtkinter.CTkLabel(
                self.root,
                text=self.text,
                font=("Arial", 20),
                text_color="black",
                bg_color= "white"
            )
            self.tip_window.place(x=-200,y=-200)
            self.tip_window.update_idletasks()
            if self.subwindow_status:
                if self.reverse:
                    tip_window_width = self.tip_window._current_width
                    if self.in_listbox:
                        self.tip_window.place_configure(x=local_x-tip_window_width-self.listbox_width,y = local_y)
                    else:
                        self.tip_window.place_configure(x=local_x-tip_window_width,y = local_y)

                else:
                    tip_window_height = self.tip_window._current_height
                    if self.in_listbox:
                        self.tip_window.place_configure(x=local_x+30,y = local_y-tip_window_height)
                    else:
                        self.tip_window.place_configure(x=local_x,y = local_y)
            else:
                if self.reverse:
                    tip_window_width = self.tip_window._current_width
                    self.tip_window.place_configure(x=local_x-tip_window_width,y = local_y+10)
                else:
                    self.tip_window.place_configure(x=local_x,y = local_y+10)
            # self.tip_window.place(x=local_x+tip_window_width/2,y = local_y)

        show_tooltip_v2(e)
        self.tip_window.bind("<Leave>",lambda e,widget = self.widget:self.really_leaving(e,widget))
    
    def really_leaving(self,e,widget):
        if self.tip_window == None:
            return
        try:
            x = widget.winfo_width()-1
            y = widget.winfo_height()-1
            if (e.x < 1 or e.x > x) or (e.y < 1 or e.y > y):
                try:
                    self.root.after(0,self.tip_window.destroy)
                    # self.tip_window.destroy()
                except Exception as e2:
                    print("error2")
                self.tip_window = None
        except Exception:
            self.root.after(0,self.tip_window.destroy)

class Month_handler:
    def __init__(self, root, month=10, year=2025):
        self.month = month
        self.year = year
        self.root = root
        self.context_menu = None
        self.week_days = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
        self.month_names = ["Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"]
        self.shift_options = ["Denní","Noční","Ranní/ stacionář","Volno","Dovolená","Osobní volno"]
        self.shift_options_short = [{"type":"D"},{"type":"N"},{"type":"R"},{"type":"/"},{"type":"DOV"},{"type":"OV"}]
        self.output_data = {"month":"","year":"","days":[]}

    def manage_option_menu(self,e,values,entry_widget,values2 = [],mirror=None,selected_day=None):
        """
        - při použití jako autosearch engine (acc_list = False) není třeba device
        - když i deletion (show funkce - oko) musí se definovat device
        """
        if self.context_menu != None:
            if self.context_menu.winfo_exists():
                self.context_menu.destroy()
                self.context_menu = None

        def on_item_selected(value,seledted_day):
            entry_widget.delete(0,200)
            entry_widget.insert(0,str(value["type"]))

            if str(value["type"]) == "D":
                entry_widget.configure(fg_color="#C0AF19")
            elif str(value["type"]) == "N":
                entry_widget.configure(fg_color="#000000")
            elif str(value["type"]) == "DOV":
                entry_widget.configure(fg_color="#1976D2")
            else:
                entry_widget.configure(fg_color="#2b2b2b")
            entry_widget.update_idletasks()
            self.root.update_idletasks()

            found = next((d for d in self.output_data["days"] if d["day_num"] == seledted_day), None)
            found["shift_type_short"] = str(value["type"])
            found["shift_type"] = self.shift_options[self.shift_options_short.index(value)]

            print(self.output_data)

            self.context_menu.destroy()
            # window.destroy()
            self.context_menu = None

        if len(values) == 0:
            return
        entry_widget.update_idletasks()
        self.root.update_idletasks()
        screen_x = self.root.winfo_pointerx()
        screen_y = self.root.winfo_pointery()

        screen_x = entry_widget.winfo_rootx()
        screen_y = entry_widget.winfo_rooty() + entry_widget.winfo_height()+5
        parent_x = self.root.winfo_rootx()
        parent_y = self.root.winfo_rooty()

        x = screen_x - parent_x + entry_widget.winfo_width()
        y = screen_y - parent_y + entry_widget.winfo_height()
        font = tkFont.Font(family="Arial", size=20)
        max_width_px = 40
        try:
            max_width_px = max(font.measure(str(val["type"])) for val in values) + 40  # Add some padding
        except Exception as e:
            pass
        window = customtkinter.CTkToplevel(self.root)
        window.overrideredirect(True)
        window.configure(bg="black")
        
        listbox = FakeContextMenu(window, values, values2, mirror=mirror, command=on_item_selected, width=max_width_px,selected_day=selected_day)
            
        listbox.pack(fill="both",expand=True)
        self.root.bind("<Button-1>", lambda e: window.destroy(), "+")
        max_visible_items = 50
        visible_items = min(len(values), max_visible_items)
        total_height = visible_items * int(listbox.one_button_height)+20
        self.root.update_idletasks()
        if total_height > self.root._current_height-20-y:
            total_height = self.root._current_height-20-y

        if mirror == True: #priznak aby pri maximalizovani nelezlo mimo obrazovku (doprava)
            screen_x=screen_x-max_width_px
        window.geometry(f"{max_width_px}x{total_height}+{screen_x}+{screen_y}")
        self.context_menu = window

    def show_one_month(self,which_month=10,which_year=2025):
        main_frame = customtkinter.CTkFrame(master=self.root,corner_radius=0,border_width=2)

        month_lable_frame = customtkinter.CTkFrame(master=main_frame,corner_radius=0)
        month_label = customtkinter.CTkLabel(master=month_lable_frame,text=f"{self.month_names[which_month-1]} {which_year}",font=("Arial", 30))
        month_label.pack(pady=10,padx=10,side="left",fill="both",anchor="w")
        month_lable_frame.pack(side="top",fill="x")

        days_frame = customtkinter.CTkFrame(master=main_frame,corner_radius=0)
        for i in range(7):
            day_label = customtkinter.CTkLabel(master=days_frame,text=self.week_days[i],font=("Arial", 20))
            day_label.pack(pady=10,side="left",fill="both",expand=True)
        days_frame.pack(side="top",fill="x")

        day_in_month = Tools.calc_days_in_month(which_month)
        start_day = Tools.get_day_of_week(which_year, which_month, 1)
        last_day = Tools.get_day_of_week(which_year, which_month, day_in_month)
        print("start day of the month: ", start_day)

        # Calculate the total number of weeks needed for the month
        self.output_data["month"] = which_month
        self.output_data["year"] = which_year
        total_days = day_in_month + start_day
        num_weeks = (total_days + 6) // 7  # Round up to the next whole week
 
        for i in range(num_weeks):
            week_frame = customtkinter.CTkFrame(master=main_frame,corner_radius=0)
            for j in range(7):
                current_day = i*7 + j - start_day + 1
                if current_day < 1 or current_day > day_in_month:
                    day_frame = customtkinter.CTkFrame(master=week_frame,corner_radius=0)
                    day_label = customtkinter.CTkLabel(master=day_frame,text="",font=("Arial", 20))
                    day_label.pack(pady=(5,0),padx=5,side="top",fill="both",expand=True)
                    day_entry = customtkinter.CTkEntry(master=day_frame,font=("Arial", 20),justify="center",fg_color="#212121",border_color="#212121",state="disabled")
                    day_entry.insert(0, "")
                    day_entry.pack(pady=(0,5),padx=5,side="top",fill="both",expand=True)
                    day_frame.pack(ipady=2,ipadx=2,pady=5,side="left",fill="both",expand=True)
                else:
                    self.output_data["days"].append({"day_num":current_day,"shift_type_short":"/"})

                    day_frame = customtkinter.CTkFrame(master=week_frame,corner_radius=0,border_width=2)
                    day_label = customtkinter.CTkLabel(master=day_frame,text=f"{current_day}",font=("Arial", 20))
                    day_label.pack(pady=(5,0),padx=5,side="top",fill="both",expand=True)
                    day_entry = customtkinter.CTkEntry(master=day_frame,font=("Arial", 20),justify="center",fg_color="#2b2b2b",border_width=0)
                    day_entry.insert(0, "/")
                    day_entry.pack(pady=(0,5),padx=5,side="top",fill="both",expand=True)

                    day_entry.bind("<Button-1>",lambda e, entry=day_entry, day = current_day: self.manage_option_menu(e,
                                                                                                                    values=self.shift_options_short,
                                                                                                                    values2=self.shift_options,
                                                                                                                    entry_widget=entry,
                                                                                                                    selected_day=day
                                                                                                                    )
                                                                                                                    )
                    
                    day_frame.pack(ipady=2,ipadx=2,pady=5,side="left",fill="both",expand=True)

                    if j == 1 or j == 3 or j == 5:
                        day_frame.configure(fg_color="#323232")

            week_frame.pack(side="top",fill="x")

        export_button = customtkinter.CTkButton(master=main_frame,text="Export data",font=("Arial", 20),command=self.export_data)
        export_button.pack(pady=10,side="top",fill="x",anchor="e",padx=10)
        main_frame.pack(fill="both", expand=True)

    def export_data(self):
        output_cleaned = []
        start_shift = ""
        end_shift = "" 
        selected_year = self.output_data["year"]
        selected_month = self.output_data["month"]
        for data in self.output_data["days"]:

            if data["shift_type_short"] == "/":
                continue
            elif data["shift_type_short"] == "D":
                start_shift = "07:00"
                end_shift = "19:00"
            elif data["shift_type_short"] == "N":
                start_shift = "19:00"
                end_shift = "07:00"
            elif data["shift_type_short"] == "R":
                start_shift = "07:00"
                end_shift = "15:00"
            else:
                start_shift = ""
                end_shift = ""

            output_cleaned.append(f"{selected_year:02d}-{selected_month:02d}-{data["day_num"]:02d},{start_shift},{end_shift},{data["shift_type"]}")

        print(output_cleaned)
        json_output = {"year_and_month":f"{selected_year:02d}-{selected_month:02d}","shifts":output_cleaned}
        json_name = f"calendar_{self.month}_{self.year}.json"
        with open(json_name, "w", encoding="utf-8") as f:
            json.dump(json_output, f, ensure_ascii=False, indent=4)
        print("Data exported to JSON file.")
        self.generate_ics(json_name)

    def generate_ics(self,json_name):
        json_path = Path(json_name)
        with json_path.open(encoding="utf-8") as f:
            data = json.load(f)

        shifts = data.get("shifts", [])
        TZ = ZoneInfo("Europe/Prague")

        def ics_escape(text: str) -> str:
            return (text
                    .replace("\\", "\\\\")
                    .replace(";", r"\;")
                    .replace(",", r"\,")
                    .replace("\n", r"\n"))

        def fmt_dt_utc(dt: datetime) -> str:
            return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        def vevent_timed(d: date, start_s: str, end_s: str, summary: str) -> str:
            uid = f"{uuid.uuid4()}@json-calendar"
            dtstamp = fmt_dt_utc(datetime.now(timezone.utc))
            h1, m1 = map(int, start_s.split(":"))
            h2, m2 = map(int, end_s.split(":"))
            start_local = datetime.combine(d, time(h1, m1), tzinfo=TZ)
            end_local = datetime.combine(d, time(h2, m2), tzinfo=TZ)
            if end_local <= start_local:
                end_local += timedelta(days=1)  # směna přes půlnoc
            return "\r\n".join([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{fmt_dt_utc(start_local)}",
                f"DTEND:{fmt_dt_utc(end_local)}",
                f"SUMMARY:{ics_escape(summary)}",
                "END:VEVENT"
            ])

        # vytvoření událostí
        events = []
        for line in shifts:
            parts = [p.strip() for p in line.split(",")]
            d = datetime.strptime(parts[0], "%Y-%m-%d").date()
            start_s, end_s, summary = parts[1], parts[2], parts[3]
            events.append(vevent_timed(d, start_s, end_s, summary))

        # sestavení ICS
        ics_content = "\r\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Calendar JSON to ICS//CZ//",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            *events,
            "END:VCALENDAR",
            ""
        ])

        # uložení do souboru
        ics_path = Path("calendar_10_2025.ics")
        ics_path.write_text(ics_content, encoding="utf-8")
        print("ICS vygenerován:", ics_path)

Month_handler(root).show_one_month(which_month=10,which_year=2025)
root.mainloop()