import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "medstock.db"
BG, NAVY, WHITE = "#eef2f7", "#14213d", "#ffffff"
TEXT, MUTED, BORDER = "#172033", "#64748b", "#d8e0ec"


def connect():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("""CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, batch TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '', quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),
        price REAL NOT NULL DEFAULT 0 CHECK(price>=0), expiry TEXT NOT NULL DEFAULT '',
        min_stock INTEGER NOT NULL DEFAULT 10 CHECK(min_stock>=0))""")
    con.execute("""CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sold_at TEXT NOT NULL, customer TEXT NOT NULL DEFAULT '',
        total REAL NOT NULL CHECK(total>=0))""")
    con.execute("""CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
        medicine_id INTEGER NOT NULL,
        medicine_name TEXT NOT NULL, batch TEXT NOT NULL DEFAULT '',
        quantity INTEGER NOT NULL CHECK(quantity>0),
        unit_price REAL NOT NULL CHECK(unit_price>=0),
        line_total REAL NOT NULL CHECK(line_total>=0))""")
    con.commit()
    return con


class MedStockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MedStock Pro | Pharmacy Management")
        self.root.geometry("1240x800")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG)
        self.cart = {}
        self._styles()
        self._header()
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=12)
        self.inventory_tab = tk.Frame(self.tabs, bg=BG)
        self.billing_tab = tk.Frame(self.tabs, bg=BG)
        self.history_tab = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.inventory_tab, text="  Inventory  ")
        self.tabs.add(self.billing_tab, text="  Billing & Sales  ")
        self.tabs.add(self.history_tab, text="  Sales History  ")
        self._build_inventory()
        self._build_billing()
        self._build_history()
        self.refresh_inventory()
        self.refresh_billing_medicines()
        self.refresh_history()

    def _styles(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("Treeview", background=WHITE, foreground=TEXT, fieldbackground=WHITE,
                    rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        s.configure("Treeview.Heading", background="#e8edf5", foreground=NAVY,
                    font=("Segoe UI", 10, "bold"), padding=(7, 9), relief="flat")
        s.map("Treeview", background=[("selected", "#dbeafe")],
              foreground=[("selected", TEXT)])
        s.configure("TEntry", padding=7, font=("Segoe UI", 10))
        s.configure("TButton", padding=(10, 7), font=("Segoe UI", 9, "bold"))
        s.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 10, "bold"))

    def _header(self):
        h = tk.Frame(self.root, bg=NAVY, height=78)
        h.pack(fill="x"); h.pack_propagate(False)
        left = tk.Frame(h, bg=NAVY); left.pack(side="left", padx=24, pady=10)
        tk.Label(left, text="MedStock Pro", bg=NAVY, fg=WHITE,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(left, text="PHARMACY INVENTORY • BILLING • SALES",
                 bg=NAVY, fg="#b8c9e8", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(h, text="LOCAL DESKTOP EDITION", bg=NAVY, fg="#dbeafe",
                 font=("Segoe UI", 9, "bold")).pack(side="right", padx=24)

    def _panel(self, parent):
        return tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)

    def _build_inventory(self):
        p = self._panel(self.inventory_tab); p.pack(fill="x", padx=8, pady=(8, 10))
        tk.Label(p, text="Medicine Details", bg=WHITE, fg=NAVY,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=4,
                                                     sticky="w", padx=14, pady=12)
        specs = [("name","Medicine name",""),("batch","Batch number",""),
                 ("category","Category",""),("quantity","Quantity in stock","0"),
                 ("price","Unit price (INR)","0.00"),("expiry","Expiry (YYYY-MM-DD)",""),
                 ("min_stock","Low-stock alert level","10")]
        self.fields = {}
        for i,(key,label,default) in enumerate(specs):
            row, col = divmod(i,4)
            cell = tk.Frame(p,bg=WHITE); cell.grid(row=row+1,column=col,sticky="ew",padx=10,pady=5)
            p.grid_columnconfigure(col,weight=1,uniform="inv")
            tk.Label(cell,text=label,bg=WHITE,fg="#475569",font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(0,4))
            e=ttk.Entry(cell); e.pack(fill="x")
            if default: e.insert(0,default)
            self.fields[key]=e
        bar=tk.Frame(p,bg="#f8fafc"); bar.grid(row=4,column=0,columnspan=4,sticky="ew",pady=(10,0))
        ttk.Button(bar,text="Add Medicine",command=self.add_medicine).pack(side="left",padx=(12,5),pady=9)
        ttk.Button(bar,text="Update Selected",command=self.update_medicine).pack(side="left",padx=5,pady=9)
        ttk.Button(bar,text="Clear Form",command=self.clear_form).pack(side="left",padx=5,pady=9)
        ttk.Button(bar,text="Delete Selected",command=self.delete_medicine).pack(side="left",padx=5,pady=9)

        toolbar=tk.Frame(self.inventory_tab,bg=BG); toolbar.pack(fill="x",padx=8,pady=(0,7))
        tk.Label(toolbar,text="Medicine Inventory",bg=BG,fg=NAVY,font=("Segoe UI",15,"bold")).pack(side="left")
        self.inv_search=tk.StringVar(); self.inv_search.trace_add("write",lambda *_:self.refresh_inventory())
        ttk.Entry(toolbar,textvariable=self.inv_search,width=28).pack(side="right",padx=(6,0))
        tk.Label(toolbar,text="Search:",bg=BG,fg=MUTED).pack(side="right")
        self.inv_table=self._tree(self.inventory_tab,[
            ("id","ID",45),("name","Medicine",190),("batch","Batch",95),("category","Category",105),
            ("quantity","Qty",65),("price","Price ₹",90),("expiry","Expiry",105),
            ("min_stock","Min stock",85),("status","Status",145)])
        self.inv_table.pack(fill="both",expand=True,padx=8,pady=(0,8))
        self.inv_table.bind("<<TreeviewSelect>>",self.select_medicine)

    def _build_billing(self):
        body=tk.Frame(self.billing_tab,bg=BG); body.pack(fill="both",expand=True,padx=8,pady=8)
        top=self._panel(body); top.pack(fill="x",pady=(0,10))
        tk.Label(top,text="Create Sale",bg=WHITE,fg=NAVY,font=("Segoe UI",15,"bold")).grid(row=0,column=0,sticky="w",padx=14,pady=10)
        tk.Label(top,text="Customer name (optional)",bg=WHITE,fg=MUTED).grid(row=1,column=0,sticky="w",padx=14)
        self.customer=ttk.Entry(top,width=35); self.customer.grid(row=2,column=0,sticky="w",padx=14,pady=(3,12))
        tk.Label(top,text="Select medicine",bg=WHITE,fg=MUTED).grid(row=1,column=1,sticky="w",padx=10)
        self.bill_medicine=ttk.Combobox(top,state="readonly",width=42)
        self.bill_medicine.grid(row=2,column=1,sticky="w",padx=10,pady=(3,12))
        tk.Label(top,text="Quantity",bg=WHITE,fg=MUTED).grid(row=1,column=2,sticky="w",padx=10)
        self.bill_qty=ttk.Entry(top,width=10); self.bill_qty.insert(0,"1")
        self.bill_qty.grid(row=2,column=2,sticky="w",padx=10,pady=(3,12))
        ttk.Button(top,text="Add to Bill",command=self.add_to_cart).grid(row=2,column=3,padx=14,pady=(3,12))
        for c,w in enumerate((2,2,1,1)): top.grid_columnconfigure(c,weight=w)

        tk.Label(body,text="Current Bill",bg=BG,fg=NAVY,font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,6))
        self.cart_table=self._tree(body,[("id","Medicine ID",85),("name","Medicine",260),
            ("batch","Batch",130),("qty","Quantity",100),("price","Unit Price ₹",130),("total","Line Total ₹",140)])
        self.cart_table.pack(fill="both",expand=True)
        bottom=self._panel(body); bottom.pack(fill="x",pady=(10,0))
        self.total_label=tk.Label(bottom,text="Bill Total: ₹0.00",bg=WHITE,fg=NAVY,font=("Segoe UI",18,"bold"))
        self.total_label.pack(side="left",padx=16,pady=12)
        ttk.Button(bottom,text="Remove Selected Item",command=self.remove_cart_item).pack(side="right",padx=8,pady=10)
        ttk.Button(bottom,text="Clear Bill",command=self.clear_cart).pack(side="right",padx=8,pady=10)
        ttk.Button(bottom,text="Complete Sale & Deduct Stock",command=self.complete_sale).pack(side="right",padx=8,pady=10)

    def _build_history(self):
        bar=tk.Frame(self.history_tab,bg=BG); bar.pack(fill="x",padx=8,pady=8)
        tk.Label(bar,text="Sales History",bg=BG,fg=NAVY,font=("Segoe UI",15,"bold")).pack(side="left")
        ttk.Button(bar,text="Export Sales CSV",command=self.export_sales).pack(side="right")
        self.history_table=self._tree(self.history_tab,[
            ("id","Sale #",80),("date","Date / Time",190),("customer","Customer",240),("total","Total ₹",140)])
        self.history_table.pack(fill="both",expand=True,padx=8,pady=(0,8))
        self.history_table.bind("<Double-1>",self.show_sale_details)

    @staticmethod
    def _tree(parent, columns):
        frame=tk.Frame(parent,bg=WHITE,highlightbackground=BORDER,highlightthickness=1)
        tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show="headings",selectmode="browse")
        for key,title,width in columns:
            tree.heading(key,text=title); tree.column(key,width=width,anchor="w" if key in ("name","batch","category","customer","date","status") else "center",stretch=key in ("name","customer"))
        y=ttk.Scrollbar(frame,orient="vertical",command=tree.yview)
        x=ttk.Scrollbar(frame,orient="horizontal",command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tree.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew")
        frame.grid_rowconfigure(0,weight=1); frame.grid_columnconfigure(0,weight=1)
        frame.tree=tree
        return frame

    def _treeview(self, frame):
        return frame.tree

    def _form_values(self):
        v={k:e.get().strip() for k,e in self.fields.items()}
        if not v["name"]: raise ValueError("Enter a medicine name.")
        try:
            v["quantity"]=int(v["quantity"]); v["price"]=float(v["price"]); v["min_stock"]=int(v["min_stock"])
        except ValueError: raise ValueError("Quantity and low-stock level must be whole numbers; price must be numeric.")
        if v["quantity"]<0 or v["price"]<0 or v["min_stock"]<0: raise ValueError("Quantity, price and low-stock level cannot be negative.")
        if v["expiry"]:
            try: datetime.strptime(v["expiry"],"%Y-%m-%d")
            except ValueError: raise ValueError("Expiry must use YYYY-MM-DD, e.g. 2027-05-31.")
        return v

    @staticmethod
    def _form_tuple(v):
        return tuple(v[k] for k in ("name","batch","category","quantity","price","expiry","min_stock"))

    def add_medicine(self):
        try:
            v=self._form_values()
            with connect() as con:
                con.execute("INSERT INTO medicines(name,batch,category,quantity,price,expiry,min_stock) VALUES(?,?,?,?,?,?,?)",self._form_tuple(v))
            self.clear_form(); self.refresh_inventory(); self.refresh_billing_medicines()
        except (ValueError,sqlite3.Error) as e: messagebox.showerror("Could not add medicine",str(e),parent=self.root)

    def selected_medicine_id(self):
        sel=self._treeview(self.inv_table).selection()
        if not sel: messagebox.showwarning("Select medicine","Select a row in inventory first.",parent=self.root); return None
        return int(self._treeview(self.inv_table).item(sel[0],"values")[0])

    def update_medicine(self):
        mid=self.selected_medicine_id()
        if mid is None:return
        try:
            v=self._form_values()
            with connect() as con: con.execute("UPDATE medicines SET name=?,batch=?,category=?,quantity=?,price=?,expiry=?,min_stock=? WHERE id=?",self._form_tuple(v)+(mid,))
            self.clear_form(); self.refresh_inventory(); self.refresh_billing_medicines()
        except (ValueError,sqlite3.Error) as e: messagebox.showerror("Could not update medicine",str(e),parent=self.root)

    def delete_medicine(self):
        mid=self.selected_medicine_id()
        if mid is None:return
        if not messagebox.askyesno("Confirm","Delete this medicine from inventory?",parent=self.root):return
        try:
            with connect() as con: con.execute("DELETE FROM medicines WHERE id=?",(mid,))
            self.clear_form(); self.refresh_inventory(); self.refresh_billing_medicines()
        except sqlite3.Error as e: messagebox.showerror("Could not delete medicine",str(e),parent=self.root)

    def select_medicine(self,event=None):
        tree=self._treeview(self.inv_table); sel=tree.selection()
        if not sel:return
        row=tree.item(sel[0],"values")
        for k,val in zip(("name","batch","category","quantity","price","expiry","min_stock"),row[1:8]):
            self.fields[k].delete(0,"end"); self.fields[k].insert(0,str(val))

    def clear_form(self):
        for e in self.fields.values():e.delete(0,"end")
        self.fields["quantity"].insert(0,"0"); self.fields["price"].insert(0,"0.00"); self.fields["min_stock"].insert(0,"10")
        for s in self._treeview(self.inv_table).selection():self._treeview(self.inv_table).selection_remove(s)
        self.fields["name"].focus_set()

    def refresh_inventory(self):
        if not hasattr(self,"inv_table"):return
        tree=self._treeview(self.inv_table)
        for i in tree.get_children():tree.delete(i)
        try:
            with connect() as con:rows=con.execute("SELECT * FROM medicines ORDER BY name COLLATE NOCASE").fetchall()
        except sqlite3.Error as e:messagebox.showerror("Database error",str(e),parent=self.root);return
        today=date.today(); q=self.inv_search.get().strip().casefold() if hasattr(self,"inv_search") else ""
        for r in rows:
            mid,name,batch,cat,qty,price,expiry,minimum=r
            status="In stock"; tag="ok"
            if expiry:
                try:
                    days=(datetime.strptime(expiry,"%Y-%m-%d").date()-today).days
                    if days<0:status="EXPIRED";tag="expired"
                    elif days<=90:status=f"Expires in {days}d";tag="soon"
                except ValueError:status="Check expiry";tag="soon"
            if qty<=minimum and tag=="ok":status="LOW STOCK";tag="low"
            tree.tag_configure("low",background="#fff7ed");tree.tag_configure("expired",background="#fee2e2");tree.tag_configure("soon",background="#fef3c7")
            if q and q not in " ".join(map(str,r)).casefold():continue
            tree.insert("","end",values=(mid,name,batch,cat,qty,f"{price:.2f}",expiry,minimum,status),tags=(tag,))

    def refresh_billing_medicines(self):
        if not hasattr(self,"bill_medicine"):return
        with connect() as con: rows=con.execute("SELECT id,name,batch,quantity,price,expiry FROM medicines WHERE quantity>0 ORDER BY name COLLATE NOCASE").fetchall()
        self.bill_options={}
        labels=[]
        for r in rows:
            mid,name,batch,qty,price,expiry=r
            label=f"{mid} | {name} | Batch {batch or '-'} | Stock {qty} | ₹{price:.2f}"
            self.bill_options[label]=r;labels.append(label)
        self.bill_medicine["values"]=labels
        if labels and self.bill_medicine.get() not in self.bill_options:self.bill_medicine.current(0)
        elif not labels:self.bill_medicine.set("")

    def add_to_cart(self):
        label=self.bill_medicine.get()
        if label not in self.bill_options:
            messagebox.showwarning("Choose medicine","Select an available medicine first.",parent=self.root);return
        try:qty=int(self.bill_qty.get().strip())
        except ValueError:messagebox.showerror("Invalid quantity","Quantity must be a whole number.",parent=self.root);return
        if qty<=0:messagebox.showerror("Invalid quantity","Quantity must be at least 1.",parent=self.root);return
        mid,name,batch,stock,price,expiry=self.bill_options[label]
        already=self.cart.get(mid,{}).get("qty",0)
        if qty+already>stock:
            messagebox.showwarning("Insufficient stock",f"Available stock for {name}: {stock}. Already in bill: {already}.",parent=self.root);return
        if expiry:
            try:
                if datetime.strptime(expiry,"%Y-%m-%d").date()<date.today():
                    messagebox.showerror("Expired medicine",f"{name} is expired and cannot be added to a bill.",parent=self.root);return
            except ValueError:
                messagebox.showerror("Check expiry","This medicine has an invalid expiry date. Correct it in Inventory first.",parent=self.root);return
        if mid in self.cart:self.cart[mid]["qty"]+=qty
        else:self.cart[mid]={"id":mid,"name":name,"batch":batch,"qty":qty,"price":float(price)}
        self.bill_qty.delete(0,"end");self.bill_qty.insert(0,"1");self.refresh_cart()

    def refresh_cart(self):
        tree=self._treeview(self.cart_table)
        for i in tree.get_children():tree.delete(i)
        total=0.0
        for mid,item in self.cart.items():
            line=item["qty"]*item["price"];total+=line
            tree.insert("","end",iid=str(mid),values=(mid,item["name"],item["batch"],item["qty"],f'{item["price"]:.2f}',f"{line:.2f}"))
        self.total_label.configure(text=f"Bill Total: ₹{total:.2f}")

    def remove_cart_item(self):
        sel=self._treeview(self.cart_table).selection()
        if not sel:messagebox.showwarning("Select item","Select a bill item to remove.",parent=self.root);return
        self.cart.pop(int(sel[0]),None);self.refresh_cart()

    def clear_cart(self):
        if self.cart and not messagebox.askyesno("Clear bill","Remove all items from the current bill?",parent=self.root):return
        self.cart.clear();self.refresh_cart()

    def complete_sale(self):
        if not self.cart:messagebox.showwarning("Empty bill","Add at least one medicine first.",parent=self.root);return
        customer=self.customer.get().strip()
        total=round(sum(x["qty"]*x["price"] for x in self.cart.values()),2)
        if not messagebox.askyesno("Confirm sale",f"Complete sale for ₹{total:.2f}?\nStock will be deducted only after confirmation.",parent=self.root):return
        try:
            with connect() as con:
                cur=con.cursor()
                # BEGIN IMMEDIATE prevents two app instances from selling the same remaining stock.
                cur.execute("BEGIN IMMEDIATE")
                for mid,item in self.cart.items():
                    row=cur.execute("SELECT name,batch,quantity,price,expiry FROM medicines WHERE id=?",(mid,)).fetchone()
                    if not row:raise ValueError(f'{item["name"]} no longer exists in inventory.')
                    name,batch,stock,price,expiry=row
                    if stock<item["qty"]:raise ValueError(f"Insufficient stock for {name}. Available: {stock}.")
                    if expiry:
                        try:
                            if datetime.strptime(expiry,"%Y-%m-%d").date()<date.today():raise ValueError(f"{name} is expired and cannot be sold.")
                        except ValueError as e:
                            if "expired" in str(e):raise
                            raise ValueError(f"{name} has an invalid expiry date; fix it before sale.")
                cur.execute("INSERT INTO sales(sold_at,customer,total) VALUES(?,?,?)",
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),customer,total))
                sale_id=cur.lastrowid
                for mid,item in self.cart.items():
                    row=cur.execute("SELECT name,batch,quantity,price FROM medicines WHERE id=?",(mid,)).fetchone()
                    name,batch,stock,price=row
                    line=round(item["qty"]*float(price),2)
                    cur.execute("INSERT INTO sale_items(sale_id,medicine_id,medicine_name,batch,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?)",
                                (sale_id,mid,name,batch,item["qty"],float(price),line))
                    cur.execute("UPDATE medicines SET quantity=quantity-? WHERE id=? AND quantity>=?",(item["qty"],mid,item["qty"]))
                    if cur.rowcount!=1:raise ValueError(f"Stock changed while processing {name}. Please retry.")
                con.commit()
            self.cart.clear();self.customer.delete(0,"end");self.refresh_cart()
            self.refresh_inventory();self.refresh_billing_medicines();self.refresh_history()
            messagebox.showinfo("Sale completed",f"Sale #{sale_id} saved successfully.\nTotal: ₹{total:.2f}\nInventory stock has been updated.",parent=self.root)
            self.tabs.select(self.history_tab)
        except (ValueError,sqlite3.Error) as e:
            messagebox.showerror("Sale not completed",f"No stock should be deducted for a failed sale.\n\n{e}",parent=self.root)

    def refresh_history(self):
        if not hasattr(self,"history_table"):return
        tree=self._treeview(self.history_table)
        for i in tree.get_children():tree.delete(i)
        with connect() as con:
            rows=con.execute("SELECT id,sold_at,customer,total FROM sales ORDER BY id DESC").fetchall()
        for r in rows:tree.insert("","end",values=(r[0],r[1],r[2] or "Walk-in customer",f"{r[3]:.2f}"))

    def show_sale_details(self,event=None):
        tree=self._treeview(self.history_table);sel=tree.selection()
        if not sel:return
        sale_id=int(tree.item(sel[0],"values")[0])
        with connect() as con:
            sale=con.execute("SELECT sold_at,customer,total FROM sales WHERE id=?",(sale_id,)).fetchone()
            items=con.execute("SELECT medicine_name,batch,quantity,unit_price,line_total FROM sale_items WHERE sale_id=?",(sale_id,)).fetchall()
        if not sale:return
        lines=[f"Sale #{sale_id}",f"Date: {sale[0]}",f"Customer: {sale[1] or 'Walk-in customer'}","", "Items:"]
        lines.extend(f"• {name} | Batch {batch or '-'} | {qty} × ₹{price:.2f} = ₹{line:.2f}" for name,batch,qty,price,line in items)
        lines.extend(["",f"TOTAL: ₹{sale[2]:.2f}"])
        messagebox.showinfo("Sale details","\n".join(lines),parent=self.root)

    def export_sales(self):
        path=filedialog.asksaveasfilename(parent=self.root,title="Export sales",defaultextension=".csv",
                                          filetypes=[("CSV files","*.csv")],initialfile=f"medstock_sales_{date.today().isoformat()}.csv")
        if not path:return
        try:
            with connect() as con:
                rows=con.execute("""SELECT s.id,s.sold_at,s.customer,i.medicine_name,i.batch,
                    i.quantity,i.unit_price,i.line_total,s.total
                    FROM sales s LEFT JOIN sale_items i ON i.sale_id=s.id ORDER BY s.id DESC,i.id""").fetchall()
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                w=csv.writer(f);w.writerow(["Sale ID","Date","Customer","Medicine","Batch","Quantity","Unit Price INR","Line Total INR","Sale Total INR"]);w.writerows(rows)
            messagebox.showinfo("Export complete",f"Sales exported to:\n{path}",parent=self.root)
        except (OSError,sqlite3.Error) as e:messagebox.showerror("Export failed",str(e),parent=self.root)


if __name__=="__main__":
    try:
        with connect() as con:
            con.execute("PRAGMA integrity_check").fetchone()
        root=tk.Tk()
        app=MedStockApp(root)
        root.mainloop()
    except Exception as exc:
        try:messagebox.showerror("MedStock Pro could not start",str(exc))
        except Exception:print(f"MedStock Pro could not start: {exc}")
