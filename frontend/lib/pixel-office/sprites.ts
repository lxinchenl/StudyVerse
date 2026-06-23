/** Pixel character templates — adapted from agent-town (MIT) procedural sprite format */

export type SpriteFrame = { width: number; height: number; data: number[][] };

export type CharacterPalette = {
  skin: string;
  hair: string;
  shirt: string;
  pants: string;
  shoes: string;
  eyes: string;
};

function parse(rows: string[]): SpriteFrame {
  const data = rows.map((row) => row.split("").map(Number));
  return { width: data[0].length, height: data.length, data };
}

const IDLE = parse([
  "000222222000",
  "002222222200",
  "002111111200",
  "001161161100",
  "001111111100",
  "000111111000",
  "000033330000",
  "000333333000",
  "011333333110",
  "011333333110",
  "000333333000",
  "000044440000",
  "000044440000",
  "000040040000",
  "000040040000",
  "000050050000",
]);

const TYPE_A = parse([
  "000222222000",
  "002222222200",
  "002111111200",
  "001161161100",
  "001111111100",
  "000111111000",
  "000033330000",
  "000333333000",
  "000333333000",
  "001333333100",
  "010333333010",
  "000044440000",
  "000044440000",
  "000040040000",
  "000040040000",
  "000050050000",
]);

const TYPE_B = parse([
  "000222222000",
  "002222222200",
  "002111111200",
  "001161161100",
  "001111111100",
  "000111111000",
  "000033330000",
  "000333333000",
  "000333333000",
  "010333333010",
  "001333333100",
  "000044440000",
  "000044440000",
  "000040040000",
  "000040040000",
  "000050050000",
]);

export const FRAMES = {
  idle: [IDLE],
  typing: [TYPE_A, TYPE_B],
  waiting: [IDLE],
  done: [IDLE],
};

const PALETTE_MAP: Record<number, keyof CharacterPalette> = {
  1: "skin",
  2: "hair",
  3: "shirt",
  4: "pants",
  5: "shoes",
  6: "eyes",
};

export function paletteFromColor(shirt: string): CharacterPalette {
  return {
    skin: "#FFDCB5",
    hair: "#2C2C2C",
    shirt,
    pants: "#34495E",
    shoes: "#2C3E50",
    eyes: "#1A1A2E",
  };
}

export function drawSprite(
  ctx: CanvasRenderingContext2D,
  frame: SpriteFrame,
  x: number,
  y: number,
  pixelSize: number,
  palette: CharacterPalette,
  flip = false
) {
  for (let row = 0; row < frame.height; row++) {
    for (let col = 0; col < frame.width; col++) {
      const idx = frame.data[row][col];
      if (idx === 0) continue;
      const key = PALETTE_MAP[idx];
      if (!key) continue;
      ctx.fillStyle = palette[key];
      const drawCol = flip ? frame.width - 1 - col : col;
      ctx.fillRect(x + drawCol * pixelSize, y + row * pixelSize, pixelSize, pixelSize);
    }
  }
}
