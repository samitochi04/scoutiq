import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { marked } from "marked";

const ScoutIQLogoPath = new URL(
  "../assets/scoutiq_pdf_logo.png",
  import.meta.url,
).href;

export async function generatePDF(report, confidence) {
  try {
    // Create a temporary container for rendering the PDF content
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

    // Create header with logo
    const header = document.createElement("div");
    header.style.textAlign = "center";
    header.style.marginBottom = "30px";
    header.style.borderBottom = "2px solid #4a6cf7";
    header.style.paddingBottom = "20px";

    const logo = document.createElement("img");
    logo.src = ScoutIQLogoPath;
    logo.style.height = "50px";
    logo.style.marginBottom = "15px";
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

    // Add confidence badge
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

    // Add report description section
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
    descContent.style.marginBottom = "0";
    descSection.appendChild(descContent);
    container.appendChild(descSection);

    // Add report body
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

    // Create a div for rendered markdown report
    const reportBody = document.createElement("div");
    reportBody.className = "pdf-report-body";
    reportBody.style.fontSize = "12px";
    reportBody.style.lineHeight = "1.8";
    reportBody.style.color = "#1c1c2e";

    // Process report content and replace em dashes
    let processedReport = report.replace(/—/g, " ");

    // Parse markdown and convert to HTML
    const htmlContent = marked.parse(processedReport);
    reportBody.innerHTML = htmlContent;

    // Style the rendered HTML elements
    const styleContent = `
      <style>
        .pdf-report-body h1 { font-size: 16px; font-weight: bold; margin: 15px 0 8px 0; color: #1a1a2e; }
        .pdf-report-body h2 { font-size: 14px; font-weight: bold; margin: 12px 0 6px 0; color: #1a1a2e; }
        .pdf-report-body h3 { font-size: 12px; font-weight: bold; margin: 10px 0 5px 0; color: #1a1a2e; }
        .pdf-report-body p { margin: 6px 0; color: #1c1c2e; font-size: 12px; }
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
    `;
    reportBody.innerHTML = styleContent + reportBody.innerHTML;

    bodySection.appendChild(reportBody);
    container.appendChild(bodySection);

    // Add footer
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

    // Convert to canvas and generate PDF
    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: "#ffffff",
    });

    const imgData = canvas.toDataURL("image/png");
    const pdf = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

    const imgWidth = 210; // A4 width in mm
    const imgHeight = (canvas.height * imgWidth) / canvas.width;
    let heightLeft = imgHeight;
    let position = 0;

    // Add pages as needed
    pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
    heightLeft -= 297; // A4 height in mm

    while (heightLeft > 0) {
      position = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= 297;
    }

    // Download the PDF
    pdf.save("scoutiq_report.pdf");

    // Clean up
    document.body.removeChild(container);
  } catch (error) {
    console.error("Error generating PDF:", error);
    throw error;
  }
}
