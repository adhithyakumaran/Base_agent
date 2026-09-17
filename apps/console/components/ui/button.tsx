import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "@radix-ui/react-slot";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--action-primary)] disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        default:
          "bg-[color:var(--action-primary)] text-[color:var(--text-inverse)] hover:bg-[color:var(--action-primary-hover)] shadow-sm",
        secondary:
          "bg-[color:var(--surface-raised)] text-[color:var(--text-primary)] border border-[color:var(--border-default)] hover:border-[color:var(--border-strong)]",
        outline:
          "border border-[color:var(--border-default)] bg-transparent text-[color:var(--text-primary)] hover:bg-[color:var(--surface-raised)]",
        ghost: "text-[color:var(--text-secondary)] hover:bg-[color:var(--surface-raised)]",
        danger:
          "bg-[color:var(--action-danger)] text-[color:var(--text-inverse)] hover:bg-[color:var(--action-danger-hover)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-lg px-6",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";
