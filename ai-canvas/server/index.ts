import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";

const app = express();
const port = Number(process.env.EXPRESS_PORT ?? 3001);

const outputsDir = path.join(process.cwd(), "outputs");
fs.mkdirSync(outputsDir, { recursive: true });

app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/transcript", (req, res) => {
  const chunk = Number(req.body?.chunk);
  const text = String(req.body?.text ?? "").trim();

  if (!Number.isFinite(chunk) || chunk < 1) {
    res.status(400).json({ ok: false, error: "Invalid chunk number." });
    return;
  }

  if (!text) {
    res.status(400).json({ ok: false, error: "Transcript text is empty." });
    return;
  }

  const file = `transcript${chunk}.txt`;
  const filePath = path.join(outputsDir, file);
  fs.writeFileSync(filePath, text, "utf8");

  res.json({ ok: true, file });
});

app.listen(port, () => {
  console.log(`Express server listening on http://localhost:${port}`);
  console.log(`Transcript outputs directory: ${outputsDir}`);
});
