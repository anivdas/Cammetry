using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Cammetry.WinUI;

internal sealed class CoreBridge : IAsyncDisposable
{
    private readonly Process _process;
    private readonly SemaphoreSlim _calls = new(1, 1);
    private int _requestId;

    public CoreBridge()
    {
        var packagedCore = Path.Combine(AppContext.BaseDirectory, "Cammetry.Core.exe");
        var usePackagedCore = File.Exists(packagedCore);
        var info = new ProcessStartInfo
        {
            FileName = usePackagedCore ? packagedCore : "python",
            Arguments = usePackagedCore ? "" : "cammetry_bridge.py",
            WorkingDirectory = usePackagedCore ? AppContext.BaseDirectory : FindRepositoryRoot(),
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        _process = Process.Start(info) ?? throw new InvalidOperationException("Cammetry Core could not be started.");
    }

    public async Task<JsonElement> CallAsync(string command, object payload, CancellationToken cancellationToken = default)
    {
        await _calls.WaitAsync(cancellationToken);
        try
        {
            var id = Interlocked.Increment(ref _requestId);
            var request = new JsonObject { ["id"] = id, ["command"] = command };
            if (JsonSerializer.SerializeToNode(payload) is JsonObject values)
                foreach (var pair in values)
                    request[pair.Key] = pair.Value?.DeepClone();
            await _process.StandardInput.WriteLineAsync(request.ToJsonString().AsMemory(), cancellationToken);
            await _process.StandardInput.FlushAsync();
            var line = await _process.StandardOutput.ReadLineAsync(cancellationToken)
                ?? throw new EndOfStreamException("Cammetry Core closed unexpectedly.");
            using var response = JsonDocument.Parse(line);
            if (!response.RootElement.GetProperty("ok").GetBoolean())
                throw new InvalidOperationException(response.RootElement.GetProperty("error").GetString());
            return response.RootElement.GetProperty("result").Clone();
        }
        finally
        {
            _calls.Release();
        }
    }

    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "cammetry_bridge.py")))
            directory = directory.Parent;
        return directory?.FullName ?? AppContext.BaseDirectory;
    }

    public async ValueTask DisposeAsync()
    {
        try
        {
            _process.StandardInput.Close();
            await _process.WaitForExitAsync();
        }
        finally
        {
            _process.Dispose();
            _calls.Dispose();
        }
    }
}
