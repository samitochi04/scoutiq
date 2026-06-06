import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { marked } from "marked";

const ScoutIQLogoPath = new URL(
  "../assets/scoutiq_pdf_logo.png",
  import.meta.url,
).href;

/**
 * Scans upward from `targetEndY` to find a row of near-white pixels,
 * so we never cut through a line of text.
 */
function findSafeCutPoint(canvas, startY, targetEndY) {
  const ctx = canvas.getContext("2d");
  // Search up to 80px above the target cut point
  const searchFrom = Math.floor(targetEndY);
  const searchTo = Math.max(startY + 1, searchFrom - 80);

  for (let y = searchFrom; y >= searchTo; y--) {
    const { data } = ctx.getImageData(0, y, canvas.width, 1);
    let isWhiteRow = true;
    for (let i = 0; i < data.length; i += 4) {
      // Allow near-white (≥245 on all channels)
      if (data[i] < 245 || data[i + 1] < 245 || data[i + 2] < 245) {
        isWhiteRow = false;
        break;
      }
    }
    if (isWhiteRow) return y;
  }

  return targetEndY; // fallback: original cut point
}

export async function generatePDF(report, confidence) {
  try {
    // ── Build the off-screen container ──────────────────────────────────────
    const container = document.createElement("div");
    container.style.position = "absolute";
    container.style.left = "-9999px";
    container.style.width = "800px";
    container.style.backgroundColor = "white";
    container.style.padding = "40px";
    container.style.fontFamily = "Arial, sans-serif";
    container.style.lineHeight = "1.6";
    container.style.color = "#1a1a2e";
    document.body.appendChild(container);

    // Header
    const header = document.createElement("div");
    header.style.textAlign = "center";
    header.style.marginBottom = "30px";
    header.style.borderBottom = "2px solid #4a6cf7";
    header.style.paddingBottom = "20px";

    const logo = document.createElement("img");
    logo.src = ScoutIQLogoPath;
    logo.style.height = "70px";
    header.appendChild(logo);

    const title = document.createElement("h1");
    title.textContent = "SCOUTING REPORT";
    title.style.margin = "10px 0";
    title.style.fontSize = "28px";
    title.style.fontWeight = "bold";
    title.style.color = "#1a1a2e";
    header.appendChild(title);

    const subtitle = document.createElement("p");
    subtitle.textContent = "Professional Player Analysis & Evaluation";
    subtitle.style.margin = "5px 0";
    subtitle.style.fontSize = "14px";
    subtitle.style.color = "#5a5a72";
    subtitle.style.fontStyle = "italic";
    header.appendChild(subtitle);

    if (confidence) {
      const confidenceDiv = document.createElement("div");
      confidenceDiv.style.marginTop = "15px";
      const confidenceLabel = document.createElement("strong");
      confidenceLabel.textContent = "Report Confidence: ";
      confidenceDiv.appendChild(confidenceLabel);

      const badge = document.createElement("span");
      const confidenceMap = {
        HIGH: { text: "HIGH", color: "#22c55e" },
        MEDIUM: { text: "MEDIUM", color: "#f59e0b" },
        LOW: { text: "LOW", color: "#ef4444" },
      };
      const conf = confidenceMap[confidence] || confidenceMap.MEDIUM;
      badge.textContent = conf.text;
      badge.style.color = conf.color;
      badge.style.fontWeight = "bold";
      confidenceDiv.appendChild(badge);
      confidenceDiv.style.fontSize = "13px";
      confidenceDiv.style.color = "#5a5a72";
      header.appendChild(confidenceDiv);
    }
    container.appendChild(header);

    // Report overview section
    const descSection = document.createElement("div");
    descSection.style.marginBottom = "25px";
    const descTitle = document.createElement("h2");
    descTitle.textContent = "REPORT OVERVIEW";
    descTitle.style.fontSize = "16px";
    descTitle.style.fontWeight = "bold";
    descTitle.style.color = "#1a1a2e";
    descTitle.style.marginBottom = "10px";
    descTitle.style.borderBottom = "1px solid #e8e8f0";
    descTitle.style.paddingBottom = "8px";
    descSection.appendChild(descTitle);

    const descContent = document.createElement("p");
    descContent.textContent =
      "This comprehensive scouting report provides an in-depth analysis of player performance, skills, and potential. Prepared by ScoutIQ, an advanced AI-powered scouting platform designed to support professional recruitment and player evaluation decisions.";
    descContent.style.fontSize = "12px";
    descContent.style.color = "#5a5a72";
    descSection.appendChild(descContent);
    container.appendChild(descSection);

    // Detailed analysis section
    const bodySection = document.createElement("div");
    bodySection.style.marginBottom = "20px";
    const bodyTitle = document.createElement("h2");
    bodyTitle.textContent = "DETAILED ANALYSIS";
    bodyTitle.style.fontSize = "16px";
    bodyTitle.style.fontWeight = "bold";
    bodyTitle.style.color = "#1a1a2e";
    bodyTitle.style.marginBottom = "10px";
    bodyTitle.style.borderBottom = "1px solid #e8e8f0";
    bodyTitle.style.paddingBottom = "8px";
    bodySection.appendChild(bodyTitle);

    const reportBody = document.createElement("div");
    reportBody.className = "pdf-report-body";
    reportBody.style.fontSize = "12px";
    reportBody.style.lineHeight = "1.8";
    reportBody.style.color = "#1c1c2e";

    const processedReport = report.replace(/—/g, " ");
    const htmlContent = marked.parse(processedReport);
    reportBody.innerHTML = `
      <style>
        .pdf-report-body h1 { font-size: 16px; font-weight: bold; margin: 15px 0 8px 0; color: #1a1a2e; }
        .pdf-report-body h2 { font-size: 14px; font-weight: bold; margin: 12px 0 6px 0; color: #1a1a2e; }
        .pdf-report-body h3 { font-size: 12px; font-weight: bold; margin: 10px 0 5px 0; color: #1a1a2e; }
        .pdf-report-body p  { margin: 6px 0; color: #1c1c2e; font-size: 12px; }
        .pdf-report-body ul, .pdf-report-body ol { margin: 8px 0; padding-left: 20px; }
        .pdf-report-body li { margin: 4px 0; }
        .pdf-report-body strong { font-weight: bold; }
        .pdf-report-body em { font-style: italic; }
        .pdf-report-body code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-family: 'Courier New', monospace; }
        .pdf-report-body blockquote { border-left: 3px solid #4a6cf7; padding-left: 12px; margin: 8px 0; color: #5a5a72; }
        .pdf-report-body table { border-collapse: collapse; width: 100%; margin: 10px 0; }
        .pdf-report-body th, .pdf-report-body td { border: 1px solid #e8e8f0; padding: 8px; text-align: left; font-size: 11px; }
        .pdf-report-body th { background: #f8f8fc; font-weight: bold; }
      </style>
      ${htmlContent}
    `;

    bodySection.appendChild(reportBody);
    container.appendChild(bodySection);

    // Footer (only rendered on the last page via canvas split below)
    const footer = document.createElement("div");
    footer.style.marginTop = "30px";
    footer.style.paddingTop = "20px";
    footer.style.borderTop = "1px solid #e8e8f0";
    footer.style.fontSize = "10px";
    footer.style.color = "#9090a8";
    footer.style.textAlign = "center";
    footer.textContent =
      "Generated by ScoutIQ | Professional AI-powered Scouting Platform | " +
      new Date().toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    container.appendChild(footer);

    // ── Render to a single full-height canvas ───────────────────────────────
    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: "#ffffff",
    });

    document.body.removeChild(container);

    // ── Slice the canvas into A4 pages with smart cut points ───────────────
    const pdf = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

    const PAGE_WIDTH_MM = 210;
    const PAGE_HEIGHT_MM = 297;
    const USABLE_HEIGHT_MM = PAGE_HEIGHT_MM - 8; // small bottom buffer before looking for a cut
    const TOP_MARGIN_MM = 10; // ← blank breathing room at top of every new page

    const pxPerMM = canvas.width / PAGE_WIDTH_MM;
    const pageHeightPx = USABLE_HEIGHT_MM * pxPerMM;
    const topMarginPx = TOP_MARGIN_MM * pxPerMM;

    let startY = 0;
    let pageIndex = 0;

    while (startY < canvas.height) {
      if (pageIndex > 0) pdf.addPage();

      const rawEndY = startY + pageHeightPx;
      const endY =
        rawEndY < canvas.height
          ? findSafeCutPoint(canvas, startY, rawEndY)
          : canvas.height;

      const sliceH = endY - startY;

      // Pages after the first get a blank top margin so content
      // doesn't crash straight into the top edge.
      const topPad = pageIndex === 0 ? 0 : topMarginPx;
      const pageCanvas = document.createElement("canvas");
      pageCanvas.width = canvas.width;
      pageCanvas.height = sliceH + topPad; // ← taller canvas to fit the margin

      const ctx = pageCanvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height);

      // Draw the slice shifted down by topPad so the margin is blank white
      ctx.drawImage(
        canvas,
        0,
        startY,
        canvas.width,
        sliceH, // source rect
        0,
        topPad,
        canvas.width,
        sliceH, // dest — offset by the top margin
      );

      const imgData = pageCanvas.toDataURL("image/png");
      const sliceHeightMM = (sliceH + topPad) / pxPerMM;

      pdf.addImage(imgData, "PNG", 0, 0, PAGE_WIDTH_MM, sliceHeightMM);

      startY = endY;
      pageIndex++;
    }

    pdf.save("scoutiq_report.pdf");
  } catch (error) {
    console.error("Error generating PDF:", error);
    throw error;
  }
}
