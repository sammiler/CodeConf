using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections.Generic; // Required for DictionaryEntry

public class DirectClangClCaller
{
    //private static StreamWriter logWriter;
    //private static string logFilePath;

    private static void LogAndConsole(string message, bool isError = false)
    {
        string logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] {(isError ? "ERROR" : "INFO")}: {message}";
        if (isError)
        {
            Console.Error.WriteLine(message);
        }
        else
        {
            Console.WriteLine(message);
        }
        //try
        //{
        //    logWriter?.WriteLine(logMessage);
        //    logWriter?.Flush();
        //}
        //catch (ObjectDisposedException)
        //{
        //    // Log writer might have been closed if an early error occurred
        //    Console.Error.WriteLine($"LogWriter was closed. Original message: {logMessage}");
        //}
        //catch (Exception ex)
        //{
        //    Console.Error.WriteLine($"Error writing to log: {ex.Message}. Original message: {logMessage}");
        //}
    }


    private static void LogConsole(string message, bool isError = false)
    {
        if (isError)
        {
            Console.Error.WriteLine(message);
        }
        else
        {
            Console.WriteLine(message);
        }
    }
    public static int Main(string[] csharpArgs)
    {
        //string logFileName = $"clang_cl_wrapper_.log";
        //string executableLocation = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
        //logFilePath = Path.Combine(executableLocation ?? Environment.CurrentDirectory, logFileName);

        //try
        //{
        //    logWriter = new StreamWriter(logFilePath, append: true, encoding: Encoding.UTF8) { AutoFlush = true };
        //}
        //catch (Exception ex)
        //{
        //    Console.Error.WriteLine($"FATAL ERROR: Could not create log file '{logFilePath}'. Exception: {ex.Message}");
        //    logWriter = null; // Ensure logWriter is null if creation fails
        //}


        string clangClPath = @"C:\Tools\clang-cl.exe";

        if (!File.Exists(clangClPath))
        {
            //logWriter?.Close();
            return -1;
        }

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = clangClPath;
        psi.WorkingDirectory = Environment.CurrentDirectory; // CMake usually changes this per compile

        // --- Hardcoded Environment Variables from cmake.bat ---
        // It's crucial that these strings are exact copies from your cmake.bat
        // Using verbatim string literals (@"...") helps with backslashes.

        // Clear existing environment variables for the process to ensure only ours are used (optional, but good for isolation)
        // psi.EnvironmentVariables.Clear(); // Uncomment if you want to start with a completely clean environment

        // Set our hardcoded environment variables
        // For PATH, it's often better to prepend so system paths are still available if needed,
        // but for INCLUDE and LIB, direct override is usually what's intended for a specific toolchain.
        string existingPath = Environment.GetEnvironmentVariable("PATH") ?? "";
        // --- End of Hardcoded Environment Variables ---


        // Add fixed -masm=att and -v for verbose output from clang-cl itself
        psi.ArgumentList.Add("-masm=att");
        psi.ArgumentList.Add("-v");
        Console.WriteLine("C# wrapper received arguments:");
        foreach (string arg in csharpArgs)
        {
            psi.ArgumentList.Add(arg);
        }

        psi.UseShellExecute = false;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.CreateNoWindow = true;


        StringBuilder argumentsForLog = new StringBuilder();
        foreach (var arg_item in psi.ArgumentList)
        {
            argumentsForLog.Append($"\"{arg_item}\" "); // Quote all args for logging clarity
        }


        int exitCode = -1;
        try
        {
            using (Process process = new Process())
            {
                process.StartInfo = psi;

                // Use anonymous methods for brevity, ensure they use LogAndConsole
                process.OutputDataReceived += (sender, e) => {
                    if (e.Data != null) LogConsole(e.Data); // 同时写入控制台和日志
                };
                process.ErrorDataReceived += (sender, e) => {
                    if (e.Data != null) LogConsole(e.Data, true); // 同时写入控制台和日志
                };

                process.Start();

                process.BeginOutputReadLine();
                process.BeginErrorReadLine();

                // You might want a timeout here if clang-cl hangs
                process.WaitForExit(); // Waits indefinitely
                exitCode = process.ExitCode;
            }
        }
        catch (Exception ex)
        {
            LogAndConsole($"--- clang-cl.exe execution failed (C# wrapper exception) ---", true);
            LogAndConsole($"C# Wrapper Exception: {ex.ToString()}", true); // Full exception details
            exitCode = -99; // Indicate wrapper-level failure
        }
        finally
        {
            LogAndConsole("--- clang-cl.exe Output End ---");
            LogAndConsole($"C# Wrapper: clang-cl.exe exited with code: {exitCode}", (exitCode != 0));
            //logWriter?.Flush();
            //logWriter?.Close();
        }
        return exitCode;
    }
}