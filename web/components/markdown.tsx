"use client";

import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

export function Markdown({ children }: { children: string }) {
  return (
    <article
      className={[
        "printable-report max-w-none text-foreground/90",
        // Headings
        "[&_h1]:text-2xl [&_h1]:font-bold [&_h1]:tracking-tight [&_h1]:mt-2 [&_h1]:mb-4 [&_h1]:pb-2 [&_h1]:border-b",
        "[&_h2]:text-lg [&_h2]:font-bold [&_h2]:tracking-tight [&_h2]:mt-7 [&_h2]:mb-2.5 [&_h2]:pb-1 [&_h2]:border-b [&_h2]:border-border/60",
        "[&_h3]:text-base [&_h3]:font-bold [&_h3]:tracking-tight [&_h3]:mt-5 [&_h3]:mb-1.5 [&_h3]:text-foreground",
        "[&_h4]:text-sm [&_h4]:font-semibold [&_h4]:uppercase [&_h4]:tracking-wider [&_h4]:text-muted-foreground [&_h4]:mt-4 [&_h4]:mb-1.5",
        // Body
        "[&_p]:my-3 [&_p]:leading-relaxed [&_p]:text-[15px]",
        "[&_strong]:font-bold [&_strong]:text-foreground",
        "[&_em]:italic [&_em]:text-foreground/80",
        // Lists
        "[&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-1",
        "[&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:space-y-1",
        "[&_li]:leading-relaxed [&_li]:text-[15px]",
        "[&_li>p]:my-1",
        // Blockquote
        "[&_blockquote]:my-4 [&_blockquote]:border-l-4 [&_blockquote]:border-primary/40 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground",
        // Code
        "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[13px] [&_code]:font-mono",
        "[&_pre]:my-4 [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:overflow-x-auto",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        // Tables
        "[&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm",
        "[&_thead]:border-b-2 [&_thead]:border-border",
        "[&_th]:p-2 [&_th]:text-left [&_th]:font-semibold [&_th]:text-foreground",
        "[&_td]:p-2 [&_td]:border-b [&_td]:border-border/40 [&_td]:align-top",
        "[&_tr:last-child_td]:border-b-0",
        // Links
        "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_a]:decoration-primary/40 hover:[&_a]:decoration-primary",
        // Horizontal rule
        "[&_hr]:my-6 [&_hr]:border-border",
      ].join(" ")}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
        {children}
      </ReactMarkdown>
    </article>
  );
}
