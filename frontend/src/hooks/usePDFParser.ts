import { useState, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";

// ── Worker Setup ─────────────────────────────────────────────────────────────
// pdfjs-dist requires a background "worker" file to do its heavy parsing work.
// We point it at the pre-built worker that ships with the library itself.
// Without this line, calling getDocument() will throw a cryptic worker error.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.mjs",
  import.meta.url
).toString();

// ── Minimum text threshold ────────────────────────────────────────────────────
// A real text PDF always has more than this.
// If we get less, it's almost certainly scanned (image-only).
const SCANNED_PDF_THRESHOLD = 100;
const BACKEND_URL = "http://127.0.0.1:8000";

// ── Return type of the hook ───────────────────────────────────────────────────
export interface PDFParseResult {
  text: string;         // The full extracted text from all pages
  fileName: string;     // Original filename e.g. "research.pdf"
  pageCount: number;    // How many pages were in the PDF
  isScanned: boolean;   // True if text was too short (likely a scanned PDF)
}

export interface UsePDFParserReturn {
  parseFile: (file: File) => Promise<PDFParseResult | null>;
  isLoading: boolean;
  statusText: string | null;
  error: string | null;
  clearError: () => void;
}

// ── The Hook ─────────────────────────────────────────────────────────────────
export function usePDFParser(): UsePDFParserReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [error, setError]         = useState<string | null>(null);

  // clearError lets the UI dismiss any error message the user has already read
  const clearError = useCallback(() => setError(null), []);

  /**
   * parseFile
   * ---------
   * Accepts a browser File object, validates it is a PDF,
   * then extracts text from every page using pdfjs-dist.
   *
   * Returns a PDFParseResult, or null if something went wrong.
   */
  const parseFile = useCallback(async (file: File): Promise<PDFParseResult | null> => {

    // ── Guard 1: Validate MIME type ───────────────────────────────────────
    // Always check the actual MIME type, not just the file extension.
    // A user could rename "virus.exe" to "virus.pdf" — the extension check
    // would pass but the MIME type check would correctly reject it.
    if (file.type !== "application/pdf") {
      setError("Only PDF files are supported. Please select a .pdf file.");
      return null;
    }

    // ── Guard 2: File size limit ──────────────────────────────────────────
    // 20 MB is a generous limit. Beyond this, parsing can freeze the browser tab.
    const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB
    if (file.size > MAX_SIZE_BYTES) {
      setError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum size is 20 MB.`);
      return null;
    }

    setIsLoading(true);
    setStatusText("Parsing locally...");
    setError(null);

    try {
      // ── Step 1: Read file as an ArrayBuffer ───────────────────────────
      // pdfjs-dist needs raw binary data, not a string.
      // FileReader is the browser API for reading local files safely.
      const arrayBuffer = await file.arrayBuffer();

      // ── Step 2: Load the PDF document ─────────────────────────────────
      // getDocument() returns a "loading task" — we await its .promise
      // to get the actual parsed PDF object.
      const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
      const pdf = await loadingTask.promise;

      const pageCount = pdf.numPages;
      const pageTexts: string[] = [];

      // ── Step 3: Extract text from every page ──────────────────────────
      // We loop through every page (1-indexed in pdfjs-dist).
      // getTextContent() returns an object with an `items` array.
      // Each item has a `str` property containing a word or fragment of text.
      for (let pageNum = 1; pageNum <= pageCount; pageNum++) {
        const page        = await pdf.getPage(pageNum);
        const textContent = await page.getTextContent();

        // Join all text fragments on this page into one string
        const pageText = textContent.items
          .map((item: unknown) => {
            if (item && typeof item === "object" && "str" in item) {
              return (item as { str: string }).str;
            }
            return "";
          })
          .join(" ")
          .trim();

        pageTexts.push(pageText);

        // Release page resources immediately — important for large PDFs
        page.cleanup();
      }

      // ── Step 4: Combine all pages into one string ─────────────────────
      const fullText = pageTexts.join("\n\n").trim();

      // ── Step 5: Destroy the PDF object to free memory ─────────────────
      // This is critical for large PDFs. Without this, parsed PDF data
      // stays in memory for the entire browser session.
      await pdf.destroy();

      // ── HYBRID FALLBACK: Server-side parsing ──────────────────────────
      // If the text is very short, it's likely a scanned document.
      // We fall back to the backend PyMuPDF parser.
      if (fullText.length < SCANNED_PDF_THRESHOLD) {
        setStatusText("Uploading for advanced parsing...");
        
        try {
          const formData = new FormData();
          formData.append("file", file);

          const response = await fetch(`${BACKEND_URL}/api/upload-pdf`, {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Server parsing failed.");
          }

          const data = await response.json();
          
          return {
            text:      data.content,
            fileName:  data.source_id,
            pageCount: data.page_count,
            isScanned: true, // We know it was scanned because it hit the fallback
          };
        } catch (serverErr: unknown) {
          console.error("[usePDFParser] Server fallback failed:", serverErr);
          const errMsg = serverErr instanceof Error ? serverErr.message : String(serverErr);
          // If the server fails, we'll just fall through and return the 
          // (likely useless) local text, but we'll show an error.
          setError(`Advanced parsing failed: ${errMsg}`);
          return null; // Return null instead of the bad text
        }
      }

      return {
        text:      fullText,
        fileName:  file.name,
        pageCount: pageCount,
        isScanned: false,
      };

    } catch (err: unknown) {
      // Translate cryptic pdfjs errors into user-friendly messages
      console.error("[usePDFParser] Error:", err);
      const errMsg = err instanceof Error ? err.message : String(err);
      
      if (errMsg.includes("Invalid PDF")) {
        setError("This file does not appear to be a valid PDF. Please try another file.");
      } else if (errMsg.includes("password")) {
        setError("This PDF is password-protected. Please remove the password and try again.");
      } else {
        setError("Failed to read the PDF file. Please try again.");
      }
      return null;
    } finally {
      // Always reset loading states — even if parsing failed
      setIsLoading(false);
      setStatusText(null);
    }
  }, []);

  return { parseFile, isLoading, statusText, error, clearError };
}
