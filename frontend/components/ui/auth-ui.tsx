"use client";

import * as React from "react";
import { useState, useId, useEffect } from "react";
import { Slot } from "@radix-ui/react-slot";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cva, type VariantProps } from "class-variance-authority";
import { Eye, EyeOff } from "lucide-react";

import { cn } from "@/lib/utils";

export interface TypewriterProps {
  text: string | string[];
  speed?: number;
  cursor?: string;
  loop?: boolean;
  deleteSpeed?: number;
  delay?: number;
  className?: string;
}

export function Typewriter({
  text,
  speed = 100,
  cursor = "",
  loop = false,
  deleteSpeed = 50,
  delay = 1500,
  className
}: TypewriterProps) {
  const [displayText, setDisplayText] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [textArrayIndex, setTextArrayIndex] = useState(0);

  const textArray = Array.isArray(text) ? text : [text];
  const currentText = textArray[textArrayIndex] || "";

  useEffect(() => {
    if (!currentText) return;

    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          if (currentIndex < currentText.length) {
            setDisplayText((prev) => prev + currentText[currentIndex]);
            setCurrentIndex((prev) => prev + 1);
          } else if (loop) {
            setTimeout(() => setIsDeleting(true), delay);
          }
        } else if (displayText.length > 0) {
          setDisplayText((prev) => prev.slice(0, -1));
        } else {
          setIsDeleting(false);
          setCurrentIndex(0);
          setTextArrayIndex((prev) => (prev + 1) % textArray.length);
        }
      },
      isDeleting ? deleteSpeed : speed
    );

    return () => clearTimeout(timeout);
  }, [currentIndex, isDeleting, currentText, loop, speed, deleteSpeed, delay, displayText, text]);

  return (
    <span className={className}>
      {displayText}
      <span className="animate-pulse">{cursor}</span>
    </span>
  );
}

const labelVariants = cva(
  "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
);

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> & VariantProps<typeof labelVariants>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root ref={ref} className={cn(labelVariants(), className)} {...props} />
));
Label.displayName = LabelPrimitive.Root.displayName;

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-12 rounded-md px-6",
        icon: "h-8 w-8"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-lg border border-input bg-background px-3 py-3 text-sm text-foreground shadow-sm shadow-black/5 transition-shadow placeholder:text-muted-foreground/70 focus-visible:bg-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export interface PasswordInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, label, ...props }, ref) => {
    const id = useId();
    const [showPassword, setShowPassword] = useState(false);
    return (
      <div className="grid w-full items-center gap-2">
        {label ? <Label htmlFor={id}>{label}</Label> : null}
        <div className="relative">
          <Input
            id={id}
            type={showPassword ? "text" : "password"}
            className={cn("pe-10", className)}
            ref={ref}
            {...props}
          />
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute inset-y-0 end-0 flex h-full w-10 items-center justify-center text-muted-foreground/80 transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-none"
            aria-label={showPassword ? "隐藏密码" : "显示密码"}
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
      </div>
    );
  }
);
PasswordInput.displayName = "PasswordInput";

export type SignUpPayload = {
  name: string;
  email: string;
  password: string;
  major: string;
};

type AuthFormContainerProps = {
  isSignIn: boolean;
  loading?: boolean;
  error?: string | null;
  onToggle: () => void;
  onSignIn: (email: string, password: string) => Promise<void>;
  onSignUp: (payload: SignUpPayload) => Promise<void>;
};

function AuthFormContainer({
  isSignIn,
  loading = false,
  error,
  onToggle,
  onSignIn,
  onSignUp
}: AuthFormContainerProps) {
  return (
    <div className="mx-auto grid w-full max-w-[380px] gap-3 px-2">
      {isSignIn ? (
        <SignInForm loading={loading} error={error} onSubmit={onSignIn} />
      ) : (
        <SignUpForm loading={loading} error={error} onSubmit={onSignUp} />
      )}
      <div className="text-center text-sm text-muted-foreground">
        {isSignIn ? "还没有账号？" : "已有账号？"}{" "}
        <Button variant="link" className="h-auto p-0 text-primary" onClick={onToggle} disabled={loading}>
          {isSignIn ? "立即注册" : "去登录"}
        </Button>
      </div>
    </div>
  );
}

function SignInForm({
  loading,
  error,
  onSubmit
}: {
  loading?: boolean;
  error?: string | null;
  onSubmit: (email: string, password: string) => Promise<void>;
}) {
  async function handleSignIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
    await onSubmit(email, password);
  }

  return (
    <form onSubmit={handleSignIn} autoComplete="on" className="flex flex-col gap-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold text-foreground">登录 StudyVerse</h1>
        <p className="text-balance text-sm text-muted-foreground">使用注册邮箱登录你的学习空间</p>
      </div>
      {error ? <p className="auth-form-error">{error}</p> : null}
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="signin-email">邮箱</Label>
          <Input
            id="signin-email"
            name="email"
            type="email"
            placeholder="you@example.com"
            required
            autoComplete="email"
            disabled={loading}
          />
        </div>
        <PasswordInput
          name="password"
          label="密码"
          required
          autoComplete="current-password"
          placeholder="请输入密码"
          disabled={loading}
        />
        <Button type="submit" className="mt-2" disabled={loading}>
          {loading ? "登录中…" : "登录"}
        </Button>
      </div>
    </form>
  );
}

function SignUpForm({
  loading,
  error,
  onSubmit
}: {
  loading?: boolean;
  error?: string | null;
  onSubmit: (payload: SignUpPayload) => Promise<void>;
}) {
  async function handleSignUp(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSubmit({
      name: String(form.get("name") || "").trim(),
      email: String(form.get("email") || "").trim(),
      password: String(form.get("password") || ""),
      major: String(form.get("major") || "").trim()
    });
  }

  return (
    <form onSubmit={handleSignUp} autoComplete="on" className="flex flex-col gap-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold text-foreground">注册新账号</h1>
        <p className="text-balance text-sm text-muted-foreground">创建账号后将拥有独立的 memory 目录</p>
      </div>
      {error ? <p className="auth-form-error">{error}</p> : null}
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="signup-name">姓名</Label>
          <Input id="signup-name" name="name" type="text" placeholder="张三" required autoComplete="name" disabled={loading} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="signup-email">邮箱</Label>
          <Input
            id="signup-email"
            name="email"
            type="email"
            placeholder="you@example.com"
            required
            autoComplete="email"
            disabled={loading}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="signup-major">专业（可选）</Label>
          <Input id="signup-major" name="major" type="text" placeholder="计算机科学与技术" autoComplete="organization" disabled={loading} />
        </div>
        <PasswordInput
          name="password"
          label="密码"
          required
          minLength={6}
          autoComplete="new-password"
          placeholder="至少 6 位"
          disabled={loading}
        />
        <Button type="submit" className="mt-2" disabled={loading}>
          {loading ? "注册中…" : "注册并登录"}
        </Button>
      </div>
    </form>
  );
}

interface AuthContentProps {
  image?: { src: string; alt: string };
  quote?: { text: string; author: string };
}

export interface AuthUIProps {
  loading?: boolean;
  error?: string | null;
  onSignIn: (email: string, password: string) => Promise<void>;
  onSignUp: (payload: SignUpPayload) => Promise<void>;
  signInContent?: AuthContentProps;
  signUpContent?: AuthContentProps;
}

const defaultSignInContent: Required<AuthContentProps> = {
  image: {
    src: "/login.png",
    alt: "登录页配图"
  },
  quote: {
    text: "欢迎回来，继续你的学习之旅",
    author: "StudyVerse"
  }
};

const defaultSignUpContent: Required<AuthContentProps> = {
  image: {
    src: "/login.png",
    alt: "登录页配图"
  },
  quote: {
    text: "开启个性化多 Agent 学习，新章节等你探索。",
    author: "StudyVerse"
  }
};

export function AuthUI({
  loading = false,
  error = null,
  onSignIn,
  onSignUp,
  signInContent = {},
  signUpContent = {}
}: AuthUIProps) {
  const [isSignIn, setIsSignIn] = useState(true);

  const finalSignInContent = {
    image: { ...defaultSignInContent.image, ...signInContent.image },
    quote: { ...defaultSignInContent.quote, ...signInContent.quote }
  };
  const finalSignUpContent = {
    image: { ...defaultSignUpContent.image, ...signUpContent.image },
    quote: { ...defaultSignUpContent.quote, ...signUpContent.quote }
  };
  const currentContent = isSignIn ? finalSignInContent : finalSignUpContent;

  return (
    <div className="auth-ui-shell w-full min-h-screen md:grid md:grid-cols-2">
      <style>{`
        input[type="password"]::-ms-reveal,
        input[type="password"]::-ms-clear {
          display: none;
        }
      `}</style>
      <div className="flex min-h-screen items-center justify-center bg-background p-6 md:min-h-0 md:p-12">
        <AuthFormContainer
          isSignIn={isSignIn}
          loading={loading}
          error={error}
          onToggle={() => setIsSignIn((prev) => !prev)}
          onSignIn={onSignIn}
          onSignUp={onSignUp}
        />
      </div>
      <div
        className="auth-ui-hero hidden md:block relative transition-all duration-500 ease-in-out"
        style={{ backgroundImage: `url(${currentContent.image.src})` }}
        key={currentContent.image.src}
      >
        <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/20 to-transparent" />
        <div className="relative z-10 flex h-full flex-col items-center justify-end p-8 pb-10">
          <blockquote className="max-w-md space-y-2 text-center text-foreground">
            <p className="text-lg font-medium">
              「
              <Typewriter key={currentContent.quote.text} text={currentContent.quote.text} speed={60} />
              」
            </p>
            <cite className="block text-sm font-light text-muted-foreground not-italic">— {currentContent.quote.author}</cite>
          </blockquote>
        </div>
      </div>
    </div>
  );
}
