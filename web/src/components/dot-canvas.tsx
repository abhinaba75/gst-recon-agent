import { useEffect, useRef } from "react";

/**
 * The dot-matrix backdrop behind the sign-in card.
 *
 * A single full-screen quad with a fragment shader that decides, per grid
 * cell, whether a dot is lit and how bright. Written to fail quietly: if
 * reduced motion is asked for, if WebGL is unavailable, or if the CDN holding
 * three.js cannot be reached, the decor simply does not appear — the card sits
 * on the page's own gradient, and nothing about signing in depends on it.
 *
 * Three is loaded from a script tag rather than bundled: it is ~600 KB for one
 * background, and the login page is the first thing a shop owner loads on a
 * phone. The cost is that the animation needs the network; the fallback above
 * is the reason that is an acceptable trade.
 */

const THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";

interface ThreeModule {
  WebGLRenderer: new (opts: Record<string, unknown>) => {
    setPixelRatio: (r: number) => void;
    setSize: (w: number, h: number) => void;
    render: (scene: unknown, camera: unknown) => void;
    dispose: () => void;
  };
  Scene: new () => { add: (o: unknown) => void };
  OrthographicCamera: new (l: number, r: number, t: number, b: number, n: number, f: number) => unknown;
  Vector2: new (x: number, y: number) => { set: (x: number, y: number) => void };
  Vector3: new (x: number, y: number, z: number) => unknown;
  PlaneGeometry: new (w: number, h: number) => { dispose: () => void };
  ShaderMaterial: new (opts: Record<string, unknown>) => { dispose: () => void };
  Mesh: new (g: unknown, m: unknown) => unknown;
  GLSL3: string;
  CustomBlending: number;
  SrcAlphaFactor: number;
  OneFactor: number;
}

declare global {
  interface Window {
    THREE?: ThreeModule;
  }
}

let loader: Promise<ThreeModule | null> | null = null;

/** Load three.js once per page, from cache if the tag is already there. */
function loadThree(): Promise<ThreeModule | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (window.THREE) return Promise.resolve(window.THREE);
  if (loader) return loader;

  loader = new Promise((resolve) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${THREE_URL}"]`);
    const script = existing ?? document.createElement("script");
    const done = () => resolve(window.THREE ?? null);
    script.addEventListener("load", done);
    script.addEventListener("error", () => resolve(null));
    if (!existing) {
      script.src = THREE_URL;
      script.async = true;
      document.head.appendChild(script);
    }
    // A CDN that never answers must not leave a promise hanging forever.
    window.setTimeout(done, 8000);
  });
  return loader;
}

const VERTEX = `
  precision mediump float;
  uniform vec2 u_resolution;
  out vec2 fragCoord;
  void main() {
    gl_Position = vec4(position, 1.0);
    fragCoord = (position.xy + 1.0) * 0.5 * u_resolution;
    fragCoord.y = u_resolution.y - fragCoord.y;
  }
`;

const FRAGMENT = `
  precision mediump float;
  in vec2 fragCoord;

  uniform float u_time;
  uniform float u_opacities[10];
  uniform vec3 u_colors[6];
  uniform float u_total_size;
  uniform float u_dot_size;
  uniform vec2 u_resolution;
  uniform int u_reverse;

  out vec4 fragColor;

  float PHI = 1.61803398874989484820459;
  float random(vec2 xy) {
      return fract(tan(distance(xy * PHI, xy) * 0.5) * xy.x);
  }

  void main() {
      vec2 st = fragCoord.xy;
      st.x -= abs(floor((mod(u_resolution.x, u_total_size) - u_dot_size) * 0.5));
      st.y -= abs(floor((mod(u_resolution.y, u_total_size) - u_dot_size) * 0.5));

      float opacity = step(0.0, st.x) * step(0.0, st.y);

      vec2 st2 = vec2(int(st.x / u_total_size), int(st.y / u_total_size));

      float frequency = 5.0;
      float show_offset = random(st2);
      float rand = random(st2 * floor((u_time / frequency) + show_offset + frequency));
      opacity *= u_opacities[int(rand * 10.0)];
      opacity *= 1.0 - step(u_dot_size / u_total_size, fract(st.x / u_total_size));
      opacity *= 1.0 - step(u_dot_size / u_total_size, fract(st.y / u_total_size));

      vec3 color = u_colors[int(show_offset * 6.0)];

      float animation_speed_factor = 3.0;
      vec2 center_grid = u_resolution / 2.0 / u_total_size;
      float dist_from_center = distance(center_grid, st2);

      float timing_offset_intro = dist_from_center * 0.01 + (random(st2) * 0.15);

      float current_timing_offset = timing_offset_intro;
      opacity *= step(current_timing_offset, u_time * animation_speed_factor);
      opacity *= clamp((1.0 - step(current_timing_offset + 0.1, u_time * animation_speed_factor)) * 1.25, 1.0, 1.25);

      fragColor = vec4(color, opacity);
      fragColor.rgb *= fragColor.a;
  }
`;

/** Dot colours per theme: brass and ink by day, warm white by night. */
const DOTS = {
  dark: [
    "0.98,0.97,0.94",
    "0.88,0.76,0.36",
    "0.98,0.97,0.94",
    "0.62,0.70,0.86",
    "0.98,0.97,0.94",
    "0.88,0.76,0.36",
  ],
  light: [
    "0.49,0.38,0.04",
    "0.07,0.38,0.21",
    "0.49,0.38,0.04",
    "0.17,0.29,0.53",
    "0.09,0.09,0.11",
    "0.49,0.38,0.04",
  ],
} as const;

function start(THREE: ThreeModule, canvas: HTMLCanvasElement, dark: boolean): () => void {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  const uniforms = {
    u_time: { value: 0 },
    u_resolution: { value: new THREE.Vector2(window.innerWidth * 2, window.innerHeight * 2) },
    u_opacities: { value: [0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8, 1.0] },
    u_colors: { value: DOTS[dark ? "dark" : "light"].map((c) => {
      const [r, g, b] = c.split(",").map(Number);
      return new THREE.Vector3(r, g, b);
    }) },
    u_total_size: { value: 20.0 },
    u_dot_size: { value: 6.0 },
    u_reverse: { value: 0 },
  };

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    uniforms,
    glslVersion: THREE.GLSL3,
    blending: THREE.CustomBlending,
    blendSrc: THREE.SrcAlphaFactor,
    blendDst: THREE.OneFactor,
    transparent: true,
  });

  const geometry = new THREE.PlaneGeometry(2, 2);
  scene.add(new THREE.Mesh(geometry, material));

  let frame = 0;
  const started = performance.now();
  const animate = () => {
    frame = requestAnimationFrame(animate);
    uniforms.u_time.value = (performance.now() - started) / 1000;
    renderer.render(scene, camera);
  };
  animate();

  const onResize = () => {
    renderer.setSize(window.innerWidth, window.innerHeight);
    uniforms.u_resolution.value.set(window.innerWidth * 2, window.innerHeight * 2);
  };
  window.addEventListener("resize", onResize);

  return () => {
    cancelAnimationFrame(frame);
    window.removeEventListener("resize", onResize);
    geometry.dispose();
    material.dispose();
    renderer.dispose();
  };
}

export function DotCanvas({ dark }: { dark: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    let active = true;
    let dispose: (() => void) | undefined;

    void loadThree().then((THREE) => {
      if (!active || !THREE || !canvasRef.current) return;
      try {
        dispose = start(THREE, canvasRef.current, dark);
      } catch {
        /* no WebGL, or a context we cannot have: the page still signs in */
      }
    });

    return () => {
      active = false;
      dispose?.();
    };
  }, [dark]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="absolute inset-0 z-0 h-full w-full"
      data-testid="dot-canvas"
    />
  );
}
