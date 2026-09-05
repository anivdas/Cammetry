using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace Cammetry.WinUI;

public sealed partial class MainWindow : Window
{
    private CoreBridge? _core;

    public MainWindow()
    {
        InitializeComponent();
        SystemBackdrop = new MicaBackdrop();
        ExtendsContentIntoTitleBar = true;
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1440, 900));
        Closed += async (_, _) =>
        {
            if (_core is not null) await _core.DisposeAsync();
        };
        _ = ConnectCoreAsync();
    }

    private async Task ConnectCoreAsync()
    {
        try
        {
            _core = new CoreBridge();
            var result = await _core.CallAsync("ping", new { });
            CoreStatus.Title = $"Connected to {result.GetProperty("name").GetString()}";
            CoreStatus.Message = "Local-only core bridge ready";
            CoreStatus.Severity = InfoBarSeverity.Success;
        }
        catch (Exception exception)
        {
            CoreStatus.Title = "Cammetry Core is unavailable";
            CoreStatus.Message = exception.Message;
            CoreStatus.Severity = InfoBarSeverity.Error;
        }
    }

    private async Task<string?> PickFolderAsync()
    {
        var picker = new FolderPicker();
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        return (await picker.PickSingleFolderAsync())?.Path;
    }

    private async void OpenDrive_Click(object sender, RoutedEventArgs e) => await OpenFolderAsync();
    private async void OpenFolder_Click(object sender, RoutedEventArgs e) => await OpenFolderAsync();
    private void OpenLibrary_Click(object sender, RoutedEventArgs e) => Navigation.SelectedItem = Navigation.MenuItems[2];

    private async Task OpenFolderAsync()
    {
        var folder = await PickFolderAsync();
        if (folder is null) return;
        CoreStatus.Title = "Scanning TeslaCam folder…";
        CoreStatus.Severity = InfoBarSeverity.Informational;
        try
        {
            if (_core is null) throw new InvalidOperationException("Cammetry Core is not connected.");
            var result = await _core.CallAsync("discover", new { root = folder });
            var groups = result.GetProperty("groups").GetArrayLength();
            CoreStatus.Title = $"Found {groups} synchronized recording groups";
            CoreStatus.Message = "Indexed locally and ready for the Viewer workspace";
            CoreStatus.Severity = InfoBarSeverity.Success;
        }
        catch (Exception exception)
        {
            CoreStatus.Title = "Could not open this folder";
            CoreStatus.Message = exception.Message;
            CoreStatus.Severity = InfoBarSeverity.Error;
        }
    }

    private void Navigation_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItemContainer?.Tag as string) ?? (args.IsSettingsSelected ? "settings" : "home");
        CoreStatus.Message = tag switch
        {
            "viewer" => "Viewer migration surface — existing Python UI remains the production fallback.",
            "library" => "Local Library service is available through Cammetry Core.",
            "incidents" => "Incident manifests and verified evidence packages are available through Cammetry Core.",
            "health" => "Compatibility and encoder checks are available through Cammetry Core.",
            "settings" => "Settings remain local to this computer.",
            _ => "Local-only core bridge ready"
        };
    }
}
