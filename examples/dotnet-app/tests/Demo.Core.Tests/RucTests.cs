using Demo.Core;

namespace Demo.Core.Tests;

public class RucTests
{
    [Theory]
    [InlineData("20131312955")]
    [InlineData("20100047218")]
    public void EsValido_RucCorrecto_DevuelveTrue(string ruc) => Assert.True(Ruc.EsValido(ruc));

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("2013131295")]
    [InlineData("20131312956")]
    [InlineData("30131312955")]
    [InlineData("2013131295A")]
    public void EsValido_RucIncorrecto_DevuelveFalse(string? ruc) => Assert.False(Ruc.EsValido(ruc));

    [Fact]
    public void CalcularDigitoVerificador_DevuelveDigitoEsperado() =>
        Assert.Equal(5, Ruc.CalcularDigitoVerificador("2013131295"));

    [Fact]
    public void CalcularDigitoVerificador_EntradaInvalida_Lanza() =>
        Assert.Throws<ArgumentException>(() => Ruc.CalcularDigitoVerificador("123"));
}
