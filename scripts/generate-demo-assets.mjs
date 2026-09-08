import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { deflateSync } from "node:zlib";

const ROOT = new URL("..", import.meta.url).pathname;
const PARTS = {
  head: [112, 142],
  torso: [142, 196],
  upper_arm_l: [52, 124],
  lower_arm_l: [48, 116],
  upper_arm_r: [52, 124],
  lower_arm_r: [48, 116],
  leg_l: [58, 142],
  leg_r: [58, 142],
  prop: [74, 160],
  preview: [320, 320]
};

const CHARACTERS = [
  {
    id: "hero_rabbit",
    palette: {
      leather: [128, 46, 39, 255],
      dark: [43, 28, 31, 255],
      paper: [239, 193, 112, 255],
      accent: [224, 132, 69, 255],
      light: [250, 227, 164, 255]
    }
  },
  {
    id: "forest_fox",
    palette: {
      leather: [45, 98, 89, 255],
      dark: [28, 48, 49, 255],
      paper: [211, 183, 107, 255],
      accent: [194, 91, 61, 255],
      light: [244, 224, 162, 255]
    }
  }
];

function crc32(buffer) {
  let crc = -1;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ -1) >>> 0;
}

function chunk(type, data = Buffer.alloc(0)) {
  const typeBuffer = Buffer.from(type);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

function writePng(filePath, width, height, draw) {
  const rgba = Buffer.alloc(width * height * 4);
  const put = (x, y, color) => {
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    const index = (Math.round(y) * width + Math.round(x)) * 4;
    rgba[index] = color[0];
    rgba[index + 1] = color[1];
    rgba[index + 2] = color[2];
    rgba[index + 3] = color[3];
  };
  const context = {
    width,
    height,
    pixel: put,
    rect(x, y, w, h, color) {
      for (let py = Math.max(0, Math.floor(y)); py < Math.min(height, Math.ceil(y + h)); py += 1) {
        for (let px = Math.max(0, Math.floor(x)); px < Math.min(width, Math.ceil(x + w)); px += 1) put(px, py, color);
      }
    },
    ellipse(cx, cy, rx, ry, color) {
      for (let py = Math.max(0, Math.floor(cy - ry)); py < Math.min(height, Math.ceil(cy + ry)); py += 1) {
        for (let px = Math.max(0, Math.floor(cx - rx)); px < Math.min(width, Math.ceil(cx + rx)); px += 1) {
          const dx = (px - cx) / rx;
          const dy = (py - cy) / ry;
          if (dx * dx + dy * dy <= 1) put(px, py, color);
        }
      }
    },
    line(x0, y0, x1, y1, thickness, color) {
      const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));
      for (let step = 0; step <= steps; step += 1) {
        const fraction = steps === 0 ? 0 : step / steps;
        this.ellipse(Math.round(x0 + (x1 - x0) * fraction), Math.round(y0 + (y1 - y0) * fraction), thickness, thickness, color);
      }
    },
    polygon(points, color) {
      const xs = points.map(([x]) => x);
      const ys = points.map(([, y]) => y);
      const minX = Math.max(0, Math.floor(Math.min(...xs)));
      const maxX = Math.min(width - 1, Math.ceil(Math.max(...xs)));
      const minY = Math.max(0, Math.floor(Math.min(...ys)));
      const maxY = Math.min(height - 1, Math.ceil(Math.max(...ys)));
      for (let py = minY; py <= maxY; py += 1) {
        for (let px = minX; px <= maxX; px += 1) {
          let inside = false;
          for (let i = 0, j = points.length - 1; i < points.length; j = i, i += 1) {
            const [xi, yi] = points[i];
            const [xj, yj] = points[j];
            if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
          }
          if (inside) put(px, py, color);
        }
      }
    },
    gradient(top, bottom) {
      for (let py = 0; py < height; py += 1) {
        const amount = py / Math.max(1, height - 1);
        const color = top.map((value, index) => Math.round(value + (bottom[index] - value) * amount));
        for (let px = 0; px < width; px += 1) put(px, py, color);
      }
    },
    grain(seed, density, colors) {
      let value = seed >>> 0;
      const total = Math.floor(width * height * density);
      for (let index = 0; index < total; index += 1) {
        value = (value * 1664525 + 1013904223) >>> 0;
        const x = value % width;
        value = (value * 1664525 + 1013904223) >>> 0;
        const y = value % height;
        put(x, y, colors[value % colors.length]);
      }
    }
  };

  draw(context);
  const scanlines = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const rowStart = y * (width * 4 + 1);
    scanlines[rowStart] = 0;
    rgba.copy(scanlines, rowStart + 1, y * width * 4, (y + 1) * width * 4);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 6;
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(scanlines)),
    chunk("IEND")
  ]));
}

function drawRabbitPart(ctx, kind, palette) {
  const { leather, dark, paper, accent, light } = palette;
  const w = ctx.width;
  const h = ctx.height;
  if (kind === "head") {
    ctx.polygon([[18, 64], [17, 12], [34, 4], [49, 46], [63, 46], [79, 4], [96, 12], [95, 65]], dark);
    ctx.polygon([[24, 57], [24, 17], [33, 13], [47, 60], [66, 60], [80, 13], [89, 17], [88, 57]], leather);
    ctx.ellipse(56, 82, 45, 49, dark);
    ctx.ellipse(56, 80, 39, 43, leather);
    ctx.ellipse(56, 83, 27, 31, paper);
    ctx.ellipse(43, 75, 5, 7, dark);
    ctx.ellipse(69, 75, 5, 7, dark);
    ctx.ellipse(43, 73, 2, 2, light);
    ctx.ellipse(69, 73, 2, 2, light);
    ctx.polygon([[51, 92], [61, 92], [56, 99]], accent);
    ctx.line(35, 104, 50, 101, 1, dark);
    ctx.line(62, 101, 77, 104, 1, dark);
    ctx.ellipse(56, 120, 9, 8, accent);
  } else if (kind === "torso") {
    ctx.polygon([[33, 8], [109, 8], [132, 60], [119, 173], [92, 191], [49, 191], [14, 173], [2, 60]], dark);
    ctx.polygon([[37, 14], [105, 14], [124, 63], [112, 169], [88, 184], [53, 184], [21, 169], [10, 63]], leather);
    ctx.polygon([[71, 21], [105, 65], [91, 155], [71, 176], [51, 155], [37, 65]], paper);
    ctx.polygon([[71, 37], [91, 67], [81, 125], [71, 143], [61, 125], [51, 67]], accent);
    ctx.line(24, 74, 118, 74, 2, dark);
    ctx.line(34, 148, 108, 148, 2, dark);
    for (let y = 46; y < 158; y += 28) {
      ctx.ellipse(31, y, 4, 4, light);
      ctx.ellipse(111, y, 4, 4, light);
    }
  } else if (kind === "prop") {
    ctx.line(37, 150, 37, 17, 5, dark);
    ctx.line(37, 146, 37, 23, 2, paper);
    ctx.polygon([[37, 2], [25, 27], [37, 22], [49, 27]], accent);
    ctx.ellipse(37, 53, 11, 14, leather);
    ctx.ellipse(37, 53, 6, 9, light);
    ctx.line(37, 65, 22, 82, 2, accent);
    ctx.line(37, 65, 51, 82, 2, accent);
  } else {
    ctx.ellipse(w / 2, h / 2, w / 2 - 2, h / 2 - 2, dark);
    ctx.ellipse(w / 2, h / 2, w / 2 - 7, h / 2 - 7, leather);
    ctx.line(w / 2, 15, w / 2, h - 15, 3, paper);
    ctx.line(w / 2 - 10, h * 0.3, w / 2 + 10, h * 0.42, 2, accent);
    ctx.line(w / 2 + 10, h * 0.58, w / 2 - 10, h * 0.7, 2, accent);
    ctx.ellipse(w / 2, 16, 5, 5, light);
    ctx.ellipse(w / 2, h - 16, 5, 5, light);
  }
}

function drawFoxPart(ctx, kind, palette) {
  const { leather, dark, paper, accent, light } = palette;
  const w = ctx.width;
  const h = ctx.height;
  if (kind === "head") {
    ctx.polygon([[12, 56], [21, 8], [51, 34], [61, 34], [91, 8], [100, 56], [94, 108], [57, 137], [18, 108]], dark);
    ctx.polygon([[18, 58], [25, 16], [51, 42], [61, 42], [87, 16], [94, 58], [88, 104], [57, 130], [24, 104]], leather);
    ctx.polygon([[28, 65], [57, 43], [84, 65], [78, 105], [57, 121], [35, 105]], paper);
    ctx.polygon([[19, 24], [27, 21], [40, 48]], accent);
    ctx.polygon([[95, 24], [87, 21], [74, 48]], accent);
    ctx.ellipse(43, 75, 5, 4, dark);
    ctx.ellipse(71, 75, 5, 4, dark);
    ctx.polygon([[52, 91], [62, 91], [57, 100]], accent);
    ctx.line(39, 105, 54, 102, 1, dark);
    ctx.line(60, 102, 75, 105, 1, dark);
    ctx.ellipse(57, 122, 8, 7, light);
  } else if (kind === "torso") {
    ctx.polygon([[20, 8], [121, 8], [138, 51], [131, 172], [102, 192], [40, 192], [10, 172], [3, 51]], dark);
    ctx.polygon([[25, 14], [117, 14], [130, 54], [123, 167], [98, 185], [45, 185], [18, 167], [11, 54]], leather);
    ctx.polygon([[71, 18], [112, 63], [105, 151], [71, 178], [37, 151], [30, 63]], paper);
    ctx.polygon([[71, 33], [98, 69], [92, 136], [71, 161], [50, 136], [44, 69]], accent);
    ctx.line(18, 88, 124, 88, 2, dark);
    ctx.line(28, 142, 114, 142, 2, dark);
    for (let x = 37; x <= 105; x += 17) ctx.ellipse(x, 44, 3, 3, light);
  } else if (kind === "prop") {
    ctx.line(37, 147, 37, 69, 4, dark);
    ctx.line(37, 147, 37, 72, 1, paper);
    ctx.polygon([[4, 70], [12, 24], [37, 9], [62, 24], [70, 70]], dark);
    ctx.polygon([[10, 67], [17, 29], [37, 16], [57, 29], [64, 67]], paper);
    for (let x = 16; x <= 58; x += 10) ctx.line(37, 65, x, 27, 1, accent);
    ctx.line(10, 67, 64, 67, 2, leather);
    ctx.ellipse(37, 151, 7, 7, accent);
  } else {
    ctx.ellipse(w / 2, h / 2, w / 2 - 2, h / 2 - 2, dark);
    ctx.ellipse(w / 2, h / 2, w / 2 - 7, h / 2 - 7, leather);
    ctx.line(w / 2, 15, w / 2, h - 15, 3, paper);
    ctx.line(w / 2 - 12, h * 0.35, w / 2 + 10, h * 0.46, 2, accent);
    ctx.line(w / 2 + 10, h * 0.56, w / 2 - 12, h * 0.67, 2, accent);
    ctx.ellipse(w / 2, 16, 5, 5, light);
    ctx.ellipse(w / 2, h - 16, 5, 5, light);
  }
}

function drawPreview(ctx, character) {
  const { palette } = character;
  ctx.gradient([232, 215, 164, 255], [166, 127, 82, 255]);
  ctx.grain(character.id === "hero_rabbit" ? 7421 : 9117, 0.028, [[221, 197, 139, 255], [244, 226, 179, 255], [183, 144, 95, 255]]);
  ctx.rect(0, 0, 320, 19, palette.dark);
  ctx.rect(0, 298, 320, 22, palette.dark);
  ctx.ellipse(160, 150, 78, 112, palette.dark);
  ctx.ellipse(160, 148, 70, 105, palette.leather);
  ctx.polygon([[160, 69], [211, 142], [194, 237], [160, 262], [126, 237], [109, 142]], palette.paper);
  ctx.polygon([[160, 88], [189, 148], [178, 212], [160, 233], [142, 212], [131, 148]], palette.accent);
  if (character.id === "hero_rabbit") {
    ctx.polygon([[113, 85], [110, 36], [132, 25], [151, 90]], palette.dark);
    ctx.polygon([[207, 85], [210, 36], [188, 25], [169, 90]], palette.dark);
    ctx.ellipse(160, 95, 52, 49, palette.dark);
    ctx.ellipse(160, 93, 45, 42, palette.leather);
    ctx.ellipse(160, 95, 30, 28, palette.paper);
  } else {
    ctx.polygon([[107, 95], [124, 42], [160, 73], [196, 42], [213, 95], [160, 144]], palette.dark);
    ctx.polygon([[115, 96], [128, 53], [160, 81], [192, 53], [205, 96], [160, 137]], palette.leather);
    ctx.polygon([[128, 100], [160, 78], [192, 100], [160, 132]], palette.paper);
  }
  ctx.ellipse(143, 96, 5, 5, palette.dark);
  ctx.ellipse(177, 96, 5, 5, palette.dark);
  ctx.line(87, 153, 232, 153, 4, palette.dark);
  ctx.line(112, 243, 208, 243, 4, palette.dark);
  ctx.ellipse(160, 274, 8, 8, palette.light);
}

function renderCharacterPart(character, kind) {
  const [width, height] = PARTS[kind];
  return (ctx) => {
    if (kind === "preview") {
      drawPreview(ctx, character);
    } else if (character.id === "hero_rabbit") {
      drawRabbitPart(ctx, kind, character.palette);
    } else {
      drawFoxPart(ctx, kind, character.palette);
    }
  };
}

function drawPaperCurtain(ctx) {
  ctx.gradient([243, 220, 162, 255], [179, 115, 72, 255]);
  ctx.grain(1729, 0.055, [[231, 201, 143, 255], [250, 232, 182, 255], [197, 143, 92, 255]]);
  ctx.rect(0, 0, ctx.width, 75, [45, 42, 40, 255]);
  ctx.rect(0, ctx.height - 84, ctx.width, 84, [47, 38, 36, 255]);
  ctx.rect(0, 65, ctx.width, 10, [187, 117, 64, 255]);
  ctx.rect(0, 75, ctx.width, 7, [243, 200, 118, 255]);
  ctx.polygon([[0, 85], [165, 85], [245, 250], [178, 630], [0, 690]], [108, 44, 43, 255]);
  ctx.polygon([[ctx.width, 85], [ctx.width - 165, 85], [ctx.width - 245, 250], [ctx.width - 178, 630], [ctx.width, 690]], [108, 44, 43, 255]);
  ctx.polygon([[0, 95], [122, 95], [178, 255], [124, 590], [0, 648]], [164, 58, 47, 255]);
  ctx.polygon([[ctx.width, 95], [ctx.width - 122, 95], [ctx.width - 178, 255], [ctx.width - 124, 590], [ctx.width, 648]], [164, 58, 47, 255]);
  for (let x = 265; x < ctx.width - 250; x += 142) {
    ctx.line(x, 105, x - 24, 602, 5, [89, 55, 42, 255]);
    ctx.line(x + 32, 105, x + 56, 602, 5, [89, 55, 42, 255]);
    ctx.ellipse(x + 16, 112, 12, 12, [225, 165, 80, 255]);
  }
  ctx.polygon([[300, 642], [530, 588], [720, 630], [920, 575], [1140, 642]], [102, 53, 39, 255]);
  ctx.line(0, 641, ctx.width, 641, 5, [240, 182, 97, 255]);
}

function drawMountainPass(ctx) {
  ctx.gradient([208, 191, 141, 255], [112, 136, 120, 255]);
  ctx.grain(2311, 0.05, [[222, 209, 164, 255], [187, 173, 130, 255], [141, 158, 139, 255]]);
  ctx.ellipse(1120, 142, 70, 70, [245, 222, 158, 255]);
  ctx.ellipse(1120, 142, 53, 53, [252, 231, 174, 255]);
  ctx.polygon([[0, 475], [190, 280], [360, 510], [540, 212], [760, 515], [980, 310], [1280, 540], [1280, 720], [0, 720]], [83, 105, 96, 255]);
  ctx.polygon([[0, 560], [228, 400], [414, 568], [667, 347], [910, 567], [1138, 380], [1280, 505], [1280, 720], [0, 720]], [47, 75, 71, 255]);
  ctx.polygon([[0, 616], [188, 505], [366, 630], [602, 471], [845, 636], [1080, 490], [1280, 601], [1280, 720], [0, 720]], [31, 57, 58, 255]);
  ctx.line(183, 550, 151, 366, 10, [30, 56, 52, 255]);
  ctx.line(151, 410, 83, 365, 6, [30, 56, 52, 255]);
  ctx.line(151, 436, 230, 387, 6, [30, 56, 52, 255]);
  ctx.line(1050, 580, 1075, 386, 9, [30, 56, 52, 255]);
  ctx.line(1070, 438, 1002, 393, 6, [30, 56, 52, 255]);
  ctx.line(1071, 461, 1146, 406, 6, [30, 56, 52, 255]);
  ctx.polygon([[604, 509], [675, 446], [747, 509]], [41, 51, 47, 255]);
  ctx.rect(622, 508, 106, 73, [63, 69, 54, 255]);
  ctx.rect(648, 530, 16, 51, [224, 182, 95, 255]);
  ctx.rect(688, 530, 16, 51, [224, 182, 95, 255]);
  ctx.rect(0, 0, ctx.width, 50, [47, 44, 40, 255]);
  ctx.rect(0, ctx.height - 52, ctx.width, 52, [42, 44, 38, 255]);
}

function drawMoonBridge(ctx) {
  ctx.gradient([41, 82, 94, 255], [25, 50, 61, 255]);
  ctx.grain(3629, 0.045, [[59, 101, 112, 255], [35, 68, 80, 255], [84, 121, 125, 255]]);
  ctx.ellipse(1002, 144, 92, 92, [242, 221, 158, 255]);
  ctx.ellipse(981, 129, 91, 91, [41, 82, 94, 255]);
  for (let i = 0; i < 28; i += 1) {
    const x = 82 + ((i * 89) % 1180);
    const y = 115 + ((i * 53) % 250);
    ctx.ellipse(x, y, i % 3 === 0 ? 3 : 2, i % 3 === 0 ? 3 : 2, [235, 218, 170, 255]);
  }
  ctx.polygon([[145, 585], [216, 510], [310, 437], [429, 372], [570, 333], [711, 367], [836, 442], [929, 514], [1003, 586]], [28, 50, 54, 255]);
  ctx.polygon([[167, 585], [237, 525], [323, 462], [435, 405], [570, 369], [694, 401], [809, 464], [901, 527], [981, 585]], [112, 73, 52, 255]);
  ctx.polygon([[228, 586], [305, 524], [389, 476], [485, 447], [570, 438], [658, 465], [746, 512], [830, 586]], [38, 68, 71, 255]);
  for (let x = 243; x < 892; x += 54) ctx.line(x, 550, x + 14, 468, 4, [39, 54, 52, 255]);
  ctx.line(170, 584, 982, 584, 8, [241, 180, 95, 255]);
  ctx.line(0, 626, ctx.width, 626, 3, [119, 165, 161, 255]);
  ctx.ellipse(236, 485, 10, 13, [234, 169, 83, 255]);
  ctx.ellipse(902, 485, 10, 13, [234, 169, 83, 255]);
  ctx.line(236, 433, 236, 475, 3, [42, 48, 44, 255]);
  ctx.line(902, 433, 902, 475, 3, [42, 48, 44, 255]);
  ctx.rect(0, 0, ctx.width, 45, [27, 42, 46, 255]);
  ctx.rect(0, ctx.height - 45, ctx.width, 45, [24, 39, 42, 255]);
}

const BACKGROUNDS = {
  paper_curtain: drawPaperCurtain,
  mountain_pass: drawMountainPass,
  moon_bridge: drawMoonBridge
};

for (const character of CHARACTERS) {
  for (const part of Object.keys(PARTS)) {
    const [width, height] = PARTS[part];
    writePng(join(ROOT, "assets", "characters", character.id, `${part}.png`), width, height, renderCharacterPart(character, part));
  }
}

for (const [id, draw] of Object.entries(BACKGROUNDS)) {
  writePng(join(ROOT, "assets", "backgrounds", `${id}.png`), 1280, 720, draw);
}

console.log("Regenerated character parts and stage scenes in assets/.");
