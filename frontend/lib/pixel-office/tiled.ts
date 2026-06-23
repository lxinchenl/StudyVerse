export interface TiledTileset {
  firstgid: number;
  columns: number;
  tilewidth: number;
  tileheight: number;
  tilecount: number;
  image: string;
}

export interface TiledTileLayer {
  name: string;
  type: string;
  visible: boolean;
  width: number;
  height: number;
  data: number[];
  opacity?: number;
}

export interface TiledMap {
  width: number;
  height: number;
  tilewidth: number;
  tileheight: number;
  layers: TiledTileLayer[];
  tilesets: TiledTileset[];
}

const FLIP_H = 0x80000000;
const FLIP_V = 0x40000000;
const FLIP_D = 0x20000000;
const FLIP_MASK = FLIP_H | FLIP_V | FLIP_D;

export interface ResolvedTile {
  tileset: TiledTileset;
  sx: number;
  sy: number;
  flipH: boolean;
  flipV: boolean;
  flipD: boolean;
}

export function parseTiledMap(raw: TiledMap): TiledMap {
  const tilesets = [...raw.tilesets].sort((a, b) => a.firstgid - b.firstgid);
  return { ...raw, tilesets };
}

export function resolveTile(gid: number, tilesets: TiledTileset[]): ResolvedTile | null {
  if (gid === 0) return null;

  const flipH = (gid & FLIP_H) !== 0;
  const flipV = (gid & FLIP_V) !== 0;
  const flipD = (gid & FLIP_D) !== 0;
  const id = gid & ~FLIP_MASK;

  let tileset: TiledTileset | null = null;
  for (let i = tilesets.length - 1; i >= 0; i--) {
    if (id >= tilesets[i].firstgid) {
      tileset = tilesets[i];
      break;
    }
  }
  if (!tileset) return null;

  const localId = id - tileset.firstgid;
  if (localId < 0 || localId >= tileset.tilecount) return null;

  const col = localId % tileset.columns;
  const row = Math.floor(localId / tileset.columns);

  return {
    tileset,
    sx: col * tileset.tilewidth,
    sy: row * tileset.tileheight,
    flipH,
    flipV,
    flipD,
  };
}

function drawFlippedTile(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  sx: number,
  sy: number,
  sw: number,
  sh: number,
  dx: number,
  dy: number,
  flipH: boolean,
  flipV: boolean,
  flipD: boolean
) {
  ctx.save();
  ctx.translate(dx + sw / 2, dy + sh / 2);
  if (flipD) {
    ctx.rotate(Math.PI / 2);
    ctx.scale(flipH ? -1 : 1, flipV ? -1 : 1);
  } else {
    ctx.scale(flipH ? -1 : 1, flipV ? -1 : 1);
  }
  ctx.drawImage(img, sx, sy, sw, sh, -sw / 2, -sh / 2, sw, sh);
  ctx.restore();
}

export function drawTiledLayer(
  ctx: CanvasRenderingContext2D,
  layer: TiledTileLayer,
  map: TiledMap,
  images: Map<string, HTMLImageElement>
) {
  if (!layer.visible || layer.type !== "tilelayer") return;

  const { tilewidth, tileheight, tilesets } = map;
  const opacity = layer.opacity ?? 1;
  const prevAlpha = ctx.globalAlpha;
  ctx.globalAlpha = prevAlpha * opacity;

  for (let y = 0; y < layer.height; y++) {
    for (let x = 0; x < layer.width; x++) {
      const gid = layer.data[y * layer.width + x];
      const tile = resolveTile(gid, tilesets);
      if (!tile) continue;

      const img = images.get(tile.tileset.image);
      if (!img) continue;

      const dx = x * tilewidth;
      const dy = y * tileheight;

      if (tile.flipH || tile.flipV || tile.flipD) {
        drawFlippedTile(
          ctx,
          img,
          tile.sx,
          tile.sy,
          tilewidth,
          tileheight,
          dx,
          dy,
          tile.flipH,
          tile.flipV,
          tile.flipD
        );
      } else {
        ctx.drawImage(img, tile.sx, tile.sy, tilewidth, tileheight, dx, dy, tilewidth, tileheight);
      }
    }
  }

  ctx.globalAlpha = prevAlpha;
}

export async function loadTiledImages(tilesets: TiledTileset[]): Promise<Map<string, HTMLImageElement>> {
  const unique = [...new Set(tilesets.map((ts) => ts.image))];
  const entries = await Promise.all(
    unique.map(
      (src) =>
        new Promise<[string, HTMLImageElement]>((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve([src, img]);
          img.onerror = () => reject(new Error(`Failed to load tileset: ${src}`));
          img.src = src;
        })
    )
  );
  return new Map(entries);
}

export function mapPixelSize(map: TiledMap) {
  return {
    width: map.width * map.tilewidth,
    height: map.height * map.tileheight,
  };
}
