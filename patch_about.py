with open("src/ui/tabs/about_tab.py", "r", encoding="utf-8") as f:
    content = f.read()

old_scroll = """        # Add mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)"""

new_scroll = """        # Add mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)"""

if old_scroll in content:
    content = content.replace(old_scroll, new_scroll)
    with open("src/ui/tabs/about_tab.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched scroll")
else:
    print("Could not patch scroll")
