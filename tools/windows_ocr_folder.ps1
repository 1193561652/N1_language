param(
    [Parameter(Mandatory=$true)][string]$ImageDir,
    [string]$Language = "ja"
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] | Out-Null

$script:AsTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and
        $_.IsGenericMethodDefinition -and
        $_.GetParameters().Count -eq 1
    } | Select-Object -First 1)

function Await-Operation {
    param(
        [Parameter(Mandatory=$true)]$Operation,
        [Parameter(Mandatory=$true)][Type]$ResultType
    )

    $task = $script:AsTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

function Read-OcrText {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Engine
    )

    $file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream = Await-Operation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await-Operation ($Engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        return $result.Text
    }
    finally {
        if ($stream) {
            $stream.Dispose()
        }
    }
}

$fullDir = [System.IO.Path]::GetFullPath($ImageDir)
$lang = [Windows.Globalization.Language]::new($Language)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {
    throw "OCR language is not available: $Language"
}

Get-ChildItem -LiteralPath $fullDir -Filter *.png | Sort-Object Name | ForEach-Object {
    $outPath = [System.IO.Path]::ChangeExtension($_.FullName, ".txt")
    $text = Read-OcrText -Path $_.FullName -Engine $engine
    [System.IO.File]::WriteAllText($outPath, $text, [System.Text.UTF8Encoding]::new($false))
    Write-Host ("OCR " + $_.Name)
}
