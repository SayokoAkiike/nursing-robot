import type { CSSProperties } from "react";

/**
 * Parses a CSS declaration string ("color:red; padding:4px") into a React
 * style object. Lets design tokens ported from the Claude Design handoff be
 * copied verbatim instead of hand-translated into camelCase objects.
 */
export function css(input: string | undefined | null): CSSProperties {
  if (!input) return {};
  const out: Record<string, string> = {};
  for (const decl of input.split(";")) {
    const idx = decl.indexOf(":");
    if (idx === -1) continue;
    const prop = decl.slice(0, idx).trim();
    const value = decl.slice(idx + 1).trim();
    if (!prop || !value) continue;
    const camel = prop.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
    out[camel] = value;
  }
  return out as CSSProperties;
}

export function mergeCss(...inputs: Array<string | undefined | null | false>): CSSProperties {
  return Object.assign({}, ...inputs.map((i) => css(i || "")));
}
