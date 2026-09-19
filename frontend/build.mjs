import { build } from 'esbuild';
import { writeFile, mkdir, readdir, rm } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.resolve(root,'../app/ui');
const result=await build({absWorkingDir:root,entryPoints:{app:'src/main.js',styles:'src/styles/index.css'},outdir:out,bundle:true,splitting:true,format:'esm',target:['es2022'],minify:true,legalComments:'none',chunkNames:'chunks/[name]-[hash]',metafile:true,write:false});
await mkdir(path.join(out,'chunks'),{recursive:true});
for(const old of await readdir(path.join(out,'chunks')))if(old.endsWith('.js'))await rm(path.join(out,'chunks',old));
for(const file of result.outputFiles)await writeFile(file.path,file.contents);
await writeFile(path.join(root,'bundle-report.json'),JSON.stringify(Object.fromEntries(result.outputFiles.map(file=>[path.relative(out,file.path).split(path.sep).join('/'),{bytes:file.contents.length,gzip:gzipSync(file.contents).length}])),null,2)+'\n');
console.log('Addon UI built from feature modules');
