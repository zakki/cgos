import resolve from "@rollup/plugin-node-resolve";
// import commonjs from '@rollup/plugin-commonjs';
import terser from "@rollup/plugin-terser";
// import typescript from '@rollup/plugin-typescript';

const banner = "/*! MIT license, more info: wgo.waltheri.net */";

export default [
  {
    input: "wgo/wgo.js",
    output: [
      {
        file: "dist/wgo.js",
        format: "iife",
        name: "wgo_module",
        sourcemap: true,
        banner,
      },
      {
        file: "dist/wgo.min.js",
        format: "iife",
        name: "wgo_module",
        sourcemap: false,
        plugins: [terser()],
        banner,
      },
    ],
    plugins: [resolve({ extensions: [".js"] })],
  },
  {
    input: "wgo/player.entry.js",
    external: [
      "./wgo",
    ],
    output: [
      {
        file: "dist/wgo.player.js",
        format: "iife",
        name: "wgo_player",
        globals: (name) => {
          if (name.endsWith("/wgo.core") || name.endsWith("/wgo")) {
            return "wgo_module";
          }
          return null;
        },
        sourcemap: true,
        banner,
      },
      {
        file: "dist/wgo.player.min.js",
        format: "iife",
        name: "wgo_player",
        globals: (name) => {
          if (name.endsWith("/wgo.core") || name.endsWith("/wgo")) {
            return "wgo_module";
          }
          return null;
        },
        sourcemap: false,
        plugins: [terser()],
        banner,
      },
    ],
    plugins: [resolve({ extensions: [".js"] })],
  },
];
