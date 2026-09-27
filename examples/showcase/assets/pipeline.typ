#set page(width: auto, height: auto, margin: 10pt, fill: none)
#let primary = rgb(sys.inputs.at("soda-primary", default: "#315b85"))
#let surface = rgb(sys.inputs.at("soda-surface", default: "#f3f5fb"))
#set text(font: "Noto Sans CJK SC", size: 18pt, fill: primary)
#let box(label) = rect(width: 118pt, height: 62pt, fill: surface, stroke: none, inset: 12pt)[#align(center + horizon)[#label]]
#grid(columns: (auto, 40pt, auto), align: horizon,
  box("源码"), align(center)[→], box("矢量图"))
