// 用法：node scripts/pdf2txt.mjs <input.pdf> <output.txt>
// 单独的 PDF 解析脚本，Python 侧通过 subprocess 调用（本机没有 PyMuPDF/pypdf）。
import fs from "node:fs";
import { PDFParse } from "pdf-parse";

const [, , input, output] = process.argv;
if (!input || !output) {
  console.error("用法: node scripts/pdf2txt.mjs <input.pdf> <output.txt>");
  process.exit(2);
}

const buf = fs.readFileSync(input);
const parser = new PDFParse({ data: buf });
const result = await parser.getText();
fs.writeFileSync(output, result.text ?? "", "utf-8");
console.log(`OK ${input} -> ${output}`);
