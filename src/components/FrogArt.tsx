type PrimitiveFrogProps = {
  size?: number;
  color?: string;
  hasBow?: boolean;
  hasTie?: boolean;
  smaller?: boolean;
  accessory?: string | null;
  containAccessory?: boolean;
  className?: string;
};

export function PrimitiveFrog({
  size = 120,
  color = "#32c832",
  hasBow = false,
  hasTie = false,
  smaller = false,
  accessory = null,
  containAccessory = false,
  className,
}: PrimitiveFrogProps) {
  const bw = size * 0.625;
  const bh = size * 0.4375;
  const bx = size * 0.125;
  const by = size * 0.3125;
  const hr = size * 0.225;
  const hx = size * 0.6875;
  const hy = size * 0.375;
  const eyeR = hr * 0.33;
  const eyeX = hx + hr * 0.28;
  const eyeY = hy - hr * 0.28;
  const legOne = { x: size * 0.0625, y: size * 0.5625, w: size * 0.3125, h: size * 0.1875 };
  const legTwo = { x: size * 0.5625, y: size * 0.5625, w: size * 0.25, h: size * 0.125 };
  const showBow = hasBow || accessory === "swamp_bow";
  const bowSize = smaller ? size * 0.1 : size * 0.15;
  const bowX = hx - hr * 0.5;
  const bowY = hy - hr * 0.78;
  const tieSize = smaller ? size * 0.08 : size * 0.12;
  const tieX = hx;
  const tieY = hy + hr - hr * 0.3;
  const showCylinder = accessory === "cylinder";
  const showCrown = accessory === "lotus_crown";
  const accessoryPadding =
    containAccessory && showCrown
      ? {
          top: size * 0.22,
          right: size * 0.1,
          bottom: size * 0.1,
          left: size * 0.1,
        }
      : containAccessory && showCylinder
        ? {
            top: size * 0.2,
            right: size * 0.1,
            bottom: size * 0.1,
            left: size * 0.1,
          }
        : { top: 0, right: 0, bottom: 0, left: 0 };
  const viewBoxX = -accessoryPadding.left;
  const viewBoxY = -accessoryPadding.top;
  const viewBoxWidth = size + accessoryPadding.left + accessoryPadding.right;
  const viewBoxHeight = size + accessoryPadding.top + accessoryPadding.bottom;
  const hatWidth = size * 0.4;
  const hatHeight = size * 0.34;
  const brimWidth = size * 0.54;
  const brimHeight = Math.max(6, size * 0.05);
  const brimY = hy - hr * (showCylinder ? 1.14 : 0.96);
  const hatTop = brimY - hatHeight + size * (showCylinder ? 0.08 : 0.1);
  const crownBaseY = hy - hr * 0.96;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      aria-hidden="true"
    >
      <g>
        <ellipse
          cx={legOne.x + legOne.w / 2}
          cy={legOne.y + legOne.h / 2}
          rx={legOne.w / 2}
          ry={legOne.h / 2}
          fill="#228b22"
        />
        <ellipse
          cx={legTwo.x + legTwo.w / 2}
          cy={legTwo.y + legTwo.h / 2}
          rx={legTwo.w / 2}
          ry={legTwo.h / 2}
          fill="#228b22"
        />
        <ellipse cx={bx + bw / 2} cy={by + bh / 2} rx={bw / 2} ry={bh / 2} fill={color} />
        <circle cx={hx} cy={hy} r={hr} fill={color} />
        <circle cx={eyeX} cy={eyeY} r={eyeR} fill="#ffffff" />
        <circle cx={eyeX + 2} cy={eyeY} r={eyeR * 0.5} fill="#111111" />

        {showCylinder && (
          <>
            <rect
              x={hx - brimWidth / 2}
              y={brimY}
              width={brimWidth}
              height={brimHeight}
              rx={brimHeight / 2}
              fill="#111111"
            />
            <rect
              x={hx - hatWidth / 2}
              y={hatTop}
              width={hatWidth}
              height={hatHeight}
              rx={size * 0.03}
              fill="#111111"
            />
            <rect
              x={hx - hatWidth / 2}
              y={hatTop + hatHeight * 0.6}
              width={hatWidth}
              height={Math.max(6, size * 0.05)}
              fill="#d4a017"
            />
          </>
        )}

        {showCrown && (
          <>
            <ellipse
              cx={hx - size * 0.12}
              cy={crownBaseY - size * 0.09}
              rx={size * 0.07}
              ry={size * 0.13}
              fill="#ffd6e9"
              transform={`rotate(-28 ${hx - size * 0.12} ${crownBaseY - size * 0.09})`}
            />
            <ellipse
              cx={hx - size * 0.04}
              cy={crownBaseY - size * 0.14}
              rx={size * 0.075}
              ry={size * 0.16}
              fill="#fff2fb"
              transform={`rotate(-12 ${hx - size * 0.04} ${crownBaseY - size * 0.14})`}
            />
            <ellipse
              cx={hx}
              cy={crownBaseY - size * 0.17}
              rx={size * 0.08}
              ry={size * 0.18}
              fill="#ffd1ef"
            />
            <ellipse
              cx={hx + size * 0.04}
              cy={crownBaseY - size * 0.14}
              rx={size * 0.075}
              ry={size * 0.16}
              fill="#fff2fb"
              transform={`rotate(12 ${hx + size * 0.04} ${crownBaseY - size * 0.14})`}
            />
            <ellipse
              cx={hx + size * 0.12}
              cy={crownBaseY - size * 0.09}
              rx={size * 0.07}
              ry={size * 0.13}
              fill="#ffd6e9"
              transform={`rotate(28 ${hx + size * 0.12} ${crownBaseY - size * 0.09})`}
            />
            <circle cx={hx} cy={crownBaseY - size * 0.11} r={size * 0.035} fill="#ffb4d9" />
            <rect
              x={hx - size * 0.17}
              y={crownBaseY - size * 0.01}
              width={size * 0.34}
              height={Math.max(6, size * 0.045)}
              rx={size * 0.025}
              fill="#f4d77d"
            />
            <circle cx={hx - size * 0.11} cy={crownBaseY + size * 0.01} r={size * 0.018} fill="#f8f1b4" />
            <circle cx={hx + size * 0.11} cy={crownBaseY + size * 0.01} r={size * 0.018} fill="#f8f1b4" />
          </>
        )}

        {showBow && (
          <>
            <circle cx={bowX - bowSize / 2} cy={bowY} r={bowSize / 2} fill="#ffc0cb" />
            <circle cx={bowX + bowSize / 2} cy={bowY} r={bowSize / 2} fill="#ffc0cb" />
            <circle cx={bowX} cy={bowY} r={bowSize / 3} fill="#dc3232" />
          </>
        )}

        {hasTie && (
          <>
            <polygon
              points={`${tieX - tieSize / 4},${tieY} ${tieX - tieSize},${tieY - tieSize / 2} ${tieX - tieSize},${tieY + tieSize / 2}`}
              fill="#6495ed"
            />
            <polygon
              points={`${tieX + tieSize / 4},${tieY} ${tieX + tieSize},${tieY - tieSize / 2} ${tieX + tieSize},${tieY + tieSize / 2}`}
              fill="#6495ed"
            />
            <circle cx={tieX} cy={tieY} r={tieSize / 4} fill="#dc3232" />
          </>
        )}
      </g>
    </svg>
  );
}

type FrogAvatarProps = {
  accessory?: string | null;
  className?: string;
  frogClassName?: string;
  frogSize?: number;
};

export function FrogAvatar({
  accessory = null,
  className,
  frogClassName,
  frogSize = 48,
}: FrogAvatarProps) {
  return (
    <span className={className} aria-hidden="true">
      <PrimitiveFrog
        size={frogSize}
        color="#32c832"
        accessory={accessory}
        containAccessory
        className={frogClassName}
      />
    </span>
  );
}

export function FrogFamily() {
  const frogs = [
    { size: 88, color: "#32c832", hasTie: true },
    { size: 88, color: "#64c864", hasBow: true },
    { size: 64, color: "#96dc96", hasBow: true, smaller: true },
    { size: 60, color: "#50b450", hasTie: true, smaller: true },
  ] as const;

  return (
    <div className="frog-family" aria-hidden="true">
      {frogs.map((frog, index) => (
        <span
          key={`${frog.size}-${frog.color}-${index}`}
          className="frog-family__member"
          style={{ width: frog.size, minHeight: 104 }}
        >
          <PrimitiveFrog {...frog} />
        </span>
      ))}
    </div>
  );
}
