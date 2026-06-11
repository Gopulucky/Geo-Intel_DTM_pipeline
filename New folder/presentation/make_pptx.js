const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Geo-Intel DTM Pipeline Team";
pptx.subject = "MoPR Hackathon PS2 Final Presentation";
pptx.title = "AI-driven DTM and Drainage Intelligence";
pptx.company = "IIT Tirupati MoPR Hackathon";
pptx.lang = "en-US";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US"
};
pptx.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });

const C = {
  bg: "071013",
  panel: "102022",
  ink: "F4FBF8",
  muted: "A9C1BA",
  green: "3DDC97",
  cyan: "37C8F2",
  amber: "F2B84B",
  red: "FF6B6B"
};

const summary = "../outputs/jobs/6967b254/devdi_ortho_Summary.png";
const hydro = "../outputs/jobs/6967b254/devdi_HydrologySummary.png";

function addBg(slide, kicker, no) {
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.bg }, line: { color: C.bg } });
  slide.addText(kicker.toUpperCase(), { x: 0.45, y: 0.32, w: 8.8, h: 0.25, fontFace: "Aptos", fontSize: 8.5, bold: true, color: C.green, charSpace: 1.6 });
  slide.addText(no, { x: 12.35, y: 0.32, w: 0.5, h: 0.2, fontSize: 8.5, bold: true, color: C.muted, align: "right" });
  slide.addShape(pptx.ShapeType.line, { x: 0.45, y: 7.02, w: 12.4, h: 0, line: { color: "2B3A3C", transparency: 20, width: 1 } });
}

function addTitle(slide, text, x, y, w, size = 34) {
  slide.addText(text, { x, y, w, h: 1.25, fontFace: "Aptos Display", fontSize: size, bold: true, color: C.ink, breakLine: false, fit: "shrink" });
}

function addBody(slide, text, x, y, w, h = 1) {
  slide.addText(text, { x, y, w, h, fontSize: 15, color: C.muted, fit: "shrink", breakLine: false });
}

function card(slide, x, y, w, h, label, title, body, accent = C.green) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: C.panel, transparency: 6 }, line: { color: "314246", transparency: 20 } });
  slide.addShape(pptx.ShapeType.rect, { x, y: y + h - 0.06, w, h: 0.06, fill: { color: accent }, line: { color: accent } });
  slide.addText(label.toUpperCase(), { x: x + 0.16, y: y + 0.16, w: w - 0.32, h: 0.2, fontSize: 7.5, bold: true, color: accent, charSpace: 1 });
  slide.addText(title, { x: x + 0.16, y: y + 0.54, w: w - 0.32, h: 0.5, fontSize: 15, bold: true, color: C.ink, fit: "shrink" });
  slide.addText(body, { x: x + 0.16, y: y + 1.12, w: w - 0.32, h: h - 1.3, fontSize: 10.5, color: C.muted, fit: "shrink" });
}

let s = pptx.addSlide();
addBg(s, "MoPR Hackathon PS2 | IIT Tirupati Final Round", "01");
addTitle(s, "AI-driven DTM and drainage intelligence for village planning", 0.55, 1.25, 6.3, 32);
addBody(s, "We convert drone point-cloud data into bare-earth terrain, hydrology layers, waterlogging hotspots, and GIS-ready drainage design outputs.", 0.6, 4.1, 5.9, 0.9);
s.addImage({ path: summary, x: 7.0, y: 1.0, w: 5.65, h: 4.8 });
s.addText("From elevation surface to drainage decision layers", { x: 7.12, y: 6.02, w: 5.35, h: 0.28, fontSize: 12, bold: true, color: C.ink, fill: { color: "071013", transparency: 15 } });

s = pptx.addSlide();
addBg(s, "Why This Matters", "02");
addTitle(s, "The hard rural planning problem is understanding how water moves.", 0.55, 0.95, 11.8, 30);
addBody(s, "Rural settlements face flooding, waterlogging and drainage gaps. Drone data is rich, but raw point clouds are too large and technical for direct planning decisions.", 0.6, 2.25, 8.8, 0.75);
card(s, 0.6, 3.35, 2.85, 2.1, "Input", "Drone point cloud", "LAS/LAZ data with millions of 3D returns.");
card(s, 3.7, 3.35, 2.85, 2.1, "Need", "Bare-earth DTM", "Remove buildings, vegetation and noise.", C.cyan);
card(s, 6.8, 3.35, 2.85, 2.1, "Insight", "Flow and hotspots", "Where water travels, slows, and accumulates.", C.amber);
card(s, 9.9, 3.35, 2.85, 2.1, "Action", "Drainage network", "GIS-ready design layers for engineering review.", C.green);

s = pptx.addSlide();
addBg(s, "Our Workflow", "03");
addTitle(s, "End-to-end automation from raw LiDAR to planning layers", 0.55, 0.86, 11.5, 30);
["Load", "Classify", "Build DTM", "Model Flow", "Detect Risk", "Design"].forEach((t, i) => {
  const x = 0.55 + i * 2.06;
  card(s, x, 2.45, 1.78, 2.5, String(i + 1), t, [
    "Chunked LAS/LAZ reading.",
    "Random Forest ground split.",
    "Interpolated GeoTIFF terrain.",
    "Flow and accumulation.",
    "Hotspots and vulnerability.",
    "Drainage vectors and parameters."
  ][i], i % 2 ? C.cyan : C.green);
});

s = pptx.addSlide();
addBg(s, "Output Evidence", "04");
addTitle(s, "One village, four linked views", 0.55, 0.92, 5.2, 30);
addBody(s, "The same terrain is viewed as elevation, flow accumulation, waterlogging depth, and drainage network. This makes the hydrology explainable to non-specialists.", 0.6, 2.1, 5.0, 1.15);
card(s, 0.6, 3.6, 1.15, 1.0, "2 m", "DTM grid", "", C.green);
card(s, 1.95, 3.6, 1.15, 1.0, "1M", "Point chunks", "", C.cyan);
card(s, 3.3, 3.6, 1.15, 1.0, "RF", "ML model", "", C.amber);
card(s, 4.65, 3.6, 1.15, 1.0, "GIS", "Outputs", "", C.green);
s.addImage({ path: summary, x: 6.3, y: 0.95, w: 6.3, h: 5.55 });

s = pptx.addSlide();
addBg(s, "Hydrology Results", "05");
s.addImage({ path: hydro, x: 0.55, y: 0.9, w: 6.2, h: 5.65 });
addTitle(s, "Hydrology turns terrain into drainage logic.", 7.05, 1.0, 5.4, 30);
addBody(s, "Flow accumulation identifies runoff concentration paths. Stream extraction creates candidate drainage alignment. Catchments split the village into manageable zones. Flood vulnerability helps prioritize construction and maintenance.", 7.1, 2.45, 5.1, 1.55);

s = pptx.addSlide();
addBg(s, "Deliverables", "06");
addTitle(s, "What we submit to evaluators", 0.55, 0.95, 11, 32);
card(s, 0.7, 2.35, 3.75, 2.2, "Automated AI/ML Processing", "Point cloud to DTM", "Ground classification, CRS handling, interpolation and raster export.", C.green);
card(s, 4.8, 2.35, 3.75, 2.2, "Optimized Drainage Network", "Design-ready vectors", "Flow paths, catchments, hotspots and drainage design parameters.", C.cyan);
card(s, 8.9, 2.35, 3.75, 2.2, "Documentation and Deployment", "Repeatable pipeline", "CLI/web wrapper, output verification, and reproducible village runs.", C.amber);
addBody(s, "Core outputs include DTM, flow direction, flow accumulation, TWI, catchments, waterlogging hotspots, drainage network, and final GeoPackage layers.", 0.75, 5.3, 11.6, 0.8);

s = pptx.addSlide();
addBg(s, "Closing", "07");
addTitle(s, "From drone data to resilient rural drainage decisions", 0.65, 1.0, 11.6, 34);
addBody(s, "Our contribution is a scalable geospatial intelligence pipeline that reduces manual terrain processing and gives planners a map stack they can inspect, validate, and act on.", 0.7, 2.45, 8.6, 1.0);
card(s, 0.8, 4.0, 2.75, 1.45, "Scalable", "Chunked processing", "Handles large LAS/LAZ files.");
card(s, 3.8, 4.0, 2.75, 1.45, "Explainable", "Layer by layer", "Visible terrain and hydrology evidence.", C.cyan);
card(s, 6.8, 4.0, 2.75, 1.45, "Interoperable", "GIS-ready", "GeoTIFF, GPKG and SHP.", C.amber);
card(s, 9.8, 4.0, 2.75, 1.45, "Useful", "Engineering bridge", "Drainage design parameters.", C.green);

pptx.writeFile({ fileName: "GeoIntel_PS2_Final_Presentation.pptx" });
