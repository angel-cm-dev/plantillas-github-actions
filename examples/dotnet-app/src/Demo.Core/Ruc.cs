namespace Demo.Core;

/// <summary>Validación del RUC peruano (11 dígitos con dígito verificador módulo 11).</summary>
public static class Ruc
{
    private static readonly int[] Pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
    private static readonly string[] PrefijosValidos = ["10", "15", "16", "17", "20"];

    public static bool EsValido(string? ruc)
    {
        if (ruc is null || ruc.Length != 11 || !ruc.All(char.IsAsciiDigit))
        {
            return false;
        }

        if (!PrefijosValidos.Contains(ruc[..2]))
        {
            return false;
        }

        return ruc[10] - '0' == CalcularDigitoVerificador(ruc[..10]);
    }

    public static int CalcularDigitoVerificador(string primeros10)
    {
        ArgumentNullException.ThrowIfNull(primeros10);
        if (primeros10.Length != 10 || !primeros10.All(char.IsAsciiDigit))
        {
            throw new ArgumentException("Se requieren 10 dígitos.", nameof(primeros10));
        }

        var suma = 0;
        for (var i = 0; i < 10; i++)
        {
            suma += (primeros10[i] - '0') * Pesos[i];
        }

        var digito = 11 - (suma % 11);
        return digito switch
        {
            10 => 0,
            11 => 1,
            _ => digito,
        };
    }
}
