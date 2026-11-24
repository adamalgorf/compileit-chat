/** The user's question, as a bubble on the right. */
export function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-muted px-4 py-2.5 text-[15px] leading-6 break-words whitespace-pre-wrap text-foreground">
        <span className="sr-only">Du: </span>
        {content}
      </p>
    </div>
  )
}
