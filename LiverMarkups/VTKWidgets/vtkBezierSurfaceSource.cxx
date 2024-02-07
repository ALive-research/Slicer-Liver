/*=========================================================================

  Program: NorMIT-Plan
  Module: vtkBezierSurfaceSource.cxx

  Copyright (c) 2017, The Intervention Centre, Oslo University Hospital

  All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met:

  1. Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.

  2. Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

  3. Neither the name of the copyright holder nor the names of its contributors
  may be used to endorse or promote products derived from this software
  without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
  =========================================================================*/
#include "vtkBezierSurfaceSource.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkObjectFactory.h>
#include <vtkInformation.h>
#include <vtkExecutive.h>
#include <vtkInformationVector.h>
#include <vtkDoubleArray.h>
#include <vtkPointData.h>

// STD includes
#include <cmath>

//-------------------------------------------------------------------------------
inline double intpow( double base, unsigned int exponent )
{
  double out = base;
  for(unsigned int i=1 ; i < exponent ; i++ )
    {
    out *= base;
    }

  return exponent==0?1:out;
}

//-------------------------------------------------------------------------------
inline long int Factorial(int n)
{
  long int fac = 1;

  for(int i=2; i<=n; ++i)
    {
    fac *= i;
    }

  return fac;
}

//-------------------------------------------------------------------------------
vtkStandardNewMacro(vtkBezierSurfaceSource);

//-------------------------------------------------------------------------------
vtkBezierSurfaceSource::vtkBezierSurfaceSource()
{
  this->SetNumberOfInputPorts(0);
  this->SetNumberOfOutputPorts(1);
  this->ControlPoints = NULL;
  this->BinomialCoefficientsX = 0;
  this->BinomialCoefficientsY = 0;

  //Note: default is bi-cubic bezier surface (cp=4x4)
  this->SetNumberOfControlPoints(4,4);
  this->SetResolution(10,10);
}

//-------------------------------------------------------------------------------
vtkBezierSurfaceSource::~vtkBezierSurfaceSource()
{
  if (this->ControlPoints != NULL)
    {

    for(unsigned int i=0; i<this->NumberOfControlPoints[0]; i++)
      {
      delete[] this->ControlPoints[i];
      }
    delete[] this->ControlPoints;
    this->ControlPoints = NULL;
    }

  if (this->BinomialCoefficientsX != NULL)
    {
    delete [] this->BinomialCoefficientsX;
    this->BinomialCoefficientsX = NULL;
    }

  if (this->BinomialCoefficientsY != NULL)
    {
    delete [] this->BinomialCoefficientsY;
    this->BinomialCoefficientsY = NULL;
    }

  this->NumberOfControlPoints[0] = 0;
  this->NumberOfControlPoints[1] = 0;
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::PrintSelf(ostream &os, vtkIndent indent)
{
  vtkPolyDataAlgorithm::PrintSelf(os, indent);

  os << "Resolution: " << this->Resolution[0] << ", " << this->Resolution[1] << "\n";

  os << "Number of Control Points : " <<
    this->NumberOfControlPoints[0] << ", " <<
    this->NumberOfControlPoints[1] << "\n";

  unsigned int xGrid = this->NumberOfControlPoints[0];
  unsigned int yGrid = this->NumberOfControlPoints[1];

  for(unsigned int i=0; i<xGrid; i++)
    {
    for(unsigned int j=0; j<yGrid; j++)
      {
      double cpt[3];
      cpt[0] = this->ControlPoints[i][j*3];
      cpt[1] = this->ControlPoints[i][j*3+1];
      cpt[2] = this->ControlPoints[i][j*3+2];

      os << "Control point[" << i << ", " << j << "] = "
         << cpt[0] << ", " << cpt[1] << ", " << cpt[2] << "\n";
      }
    os << "\n";
    }

  for(unsigned int i=0; i<xGrid; i++)
    {
    os << "Binomial coefficient X[" << i << "] = "
       << this->BinomialCoefficientsX[i] << "\n";
    }

  for(unsigned int i=0; i<yGrid; i++)
    {
    os << "Binomial coefficient Y[" << i << "] = "
       << this->BinomialCoefficientsY[i] << "\n";
    }
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::SetControlPoints(vtkPoints *points)
{
  for(unsigned int i=0; i<this->NumberOfControlPoints[0]; i++)
    {
    for(unsigned int j=0; j<this->NumberOfControlPoints[1]; j++)
      {
      double *point = points->GetPoint(i*this->NumberOfControlPoints[1]+j);
      this->ControlPoints[i][j*3]   = point[0];
      this->ControlPoints[i][j*3+1] = point[1];
      this->ControlPoints[i][j*3+2] = point[2];
      }
    }

  this->Modified();
}


//-------------------------------------------------------------------------------
vtkSmartPointer<vtkPoints>
vtkBezierSurfaceSource::GetControlPoints() const
{
  vtkSmartPointer<vtkPoints> points = vtkSmartPointer<vtkPoints>::New();

  for(unsigned int i=0; i<this->NumberOfControlPoints[0]; i++)
    {
    for(unsigned int j=0; j<this->NumberOfControlPoints[1]; j++)
      {
        double point[3] = {this->ControlPoints[i][j*3],
                           this->ControlPoints[i][j*3+1],
                           this->ControlPoints[i][j*3+2]};
        points->InsertPoint(i*this->NumberOfControlPoints[1]+j,point);
      }
    }

  return points;
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::SetNumberOfControlPoints(unsigned int m, unsigned int n)
{
  if (this->NumberOfControlPoints[0] == m && this->NumberOfControlPoints[1] == n)
    {
    return;
    }

  if (this->ControlPoints != NULL)
    {
    for(unsigned int i=0; i<this->NumberOfControlPoints[0]; i++)
      {
      delete[] this->ControlPoints[i];
      }
    delete [] this->ControlPoints;
    }

  if (this->BinomialCoefficientsX != NULL)
    {
    delete [] this->BinomialCoefficientsX;
    this->BinomialCoefficientsX = NULL;
    }

  if (this->BinomialCoefficientsY != NULL)
    {
    delete [] this->BinomialCoefficientsY;
    this->BinomialCoefficientsY = NULL;
    }

  //Assignment of less than 2 control points in any dimension will result in 2
  //control points
  this->NumberOfControlPoints[0] = (m<2) ? 2 : m;
  this->NumberOfControlPoints[1] = (n<2) ? 2 : n;

  this->ControlPoints = new double*[this->NumberOfControlPoints[0]];
  for(unsigned int i=0; i<m; i++)
    {
    this->ControlPoints[i] = new double[n*3];
    }

  this->ResetControlPoints();
  this->BinomialCoefficientsX = new double[m];
  this->BinomialCoefficientsY = new double[n];
  this->ComputeBinomialCoefficients();
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::ResetControlPoints()
{
  unsigned int m = this->NumberOfControlPoints[0];
  unsigned int n = this->NumberOfControlPoints[1];

  double distx = 1.0 / static_cast<double>(m-1);
  double disty = 1.0 / static_cast<double>(n-1);

  for (unsigned int i=0; i<m; i++)
    {
    for (unsigned int j=0; j<n; j++)
      {
      double *pt = this->ControlPoints[i]+j*3;
      pt[0] = -0.5 + i*distx;
      pt[1] = -0.5 + j*disty;
      pt[2] = 0.0;
      }
    }

  this->Modified();
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::SetResolution(unsigned int x, unsigned int y)
{
  if (this->Resolution[0] == x && this->Resolution[1] == y)
    {
    return;
    }

  this->Resolution[0] = x;
  this->Resolution[1] = y;

  this->DataArray = vtkSmartPointer<vtkDoubleArray>::New();
  this->DataArray->SetNumberOfComponents(3);
  this->DataArray->SetNumberOfTuples(x*y);
  this->UpdateTopology();

  this->TCoords = vtkSmartPointer<vtkFloatArray>::New();
  this->TCoords->SetNumberOfComponents(2);
  this->TCoords->SetNumberOfTuples(x*y);

  this->Modified();
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::GetResolution(unsigned int resolution[2]) const
{
  resolution[0] = this->Resolution[0];
  resolution[1] = this->Resolution[1];
}

//-------------------------------------------------------------------------------
int vtkBezierSurfaceSource::RequestData(vtkInformation *vtkNotUsed(request),
                                        vtkInformationVector **vtkNotUsed(inputVector),
                                        vtkInformationVector *outputVector)
{
  vtkInformation *bezierSurfaceOutputInfo = outputVector->GetInformationObject(0);
  if (bezierSurfaceOutputInfo)
    {
    vtkPolyData *bezierSurfaceOutput =
      vtkPolyData::SafeDownCast(bezierSurfaceOutputInfo->Get(vtkDataObject::DATA_OBJECT()));
    this->UpdateBezierSurfacePolyData(bezierSurfaceOutput);
    bezierSurfaceOutput->SetPolys(this->Topology);
    }

  return 1;
}

// //-------------------------------------------------------------------------------
// void vtkBezierSurfaceSource::UpdateTopology()
// {
//   unsigned int xRes = this->Resolution[0];
//   unsigned int yRes = this->Resolution[1];

//   this->Topology = vtkSmartPointer<vtkCellArray>::New();

//   for (unsigned int i=0; i<xRes-1; i++)
//     {
//     for (unsigned int j=0; j<yRes-1; j++)
//       {
//       unsigned int base = i*yRes + j;
//       unsigned int a = base;
//       unsigned int b = base + 1;
//       unsigned int c = base + yRes + 1;
//       unsigned int d = base + yRes;
//       vtkIdType triangle[3];

//       triangle[0] = c;
//       triangle[1] = b;
//       triangle[2] = a;
//       Topology->InsertNextCell(3, triangle);

//       triangle[0] = d;
//       triangle[1] = c;
//       triangle[2] = a;
//       Topology->InsertNextCell(3, triangle);
//       }
//     }
// }

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::UpdateTopology()
{
  unsigned int xRes = this->Resolution[0];
  unsigned int yRes = this->Resolution[1];

  this->Topology = vtkSmartPointer<vtkCellArray>::New();

  for (unsigned int i=0; i<xRes-1; i++)
    {
    for (unsigned int j=0; j<yRes-1; j++)
      {
      unsigned int base = i*yRes + j;
      unsigned int a = base;
      unsigned int b = base + 1;
      unsigned int c = base + yRes + 1;
      unsigned int d = base + yRes;
      vtkIdType quad[4];

      quad[0] = d;
      quad[1] = c;
      quad[2] = b;
      quad[3] = a;
      Topology->InsertNextCell(4, quad);
      }
    }
}


//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::ComputeBinomialCoefficients()
{
  unsigned int xGrid = this->NumberOfControlPoints[0];
  unsigned int yGrid = this->NumberOfControlPoints[1];

#pragma omp parallel for
  for (unsigned int i=0; i<xGrid; i++)
    {
    this->BinomialCoefficientsX[i] =
      Factorial(xGrid-1) /
      static_cast<double>(Factorial(i)*Factorial(xGrid-i-1));
    }
  //END parallell for

  if (xGrid != yGrid)
    {
#pragma omp parallel for
    for (unsigned int i=0; i<yGrid; i++)
      {
      this->BinomialCoefficientsY[i] =
        Factorial(yGrid-1) /
        static_cast<double>(Factorial(i)*Factorial(yGrid-i-1));
      }
    }
  else
    {
#pragma omp parallel for
    for (unsigned int i=0; i<xGrid; i++)
      {
      this->BinomialCoefficientsY[i] = this->BinomialCoefficientsX[i];
      }
    //END parallell for
    }
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::UpdateBezierSurfacePolyData(vtkPolyData *polyData)
{
  if (polyData == NULL)
    {
    return;
    }

  vtkSmartPointer<vtkPoints> surfacePoints =
    vtkSmartPointer<vtkPoints>::New();

  this->EvaluateBezierSurface(surfacePoints);
  polyData->SetPoints(surfacePoints);
  polyData->GetPointData()->SetTCoords(this->TCoords);
}

//-------------------------------------------------------------------------------
void vtkBezierSurfaceSource::EvaluateBezierSurface(vtkPoints *points)
{
  unsigned int xGrid = this->NumberOfControlPoints[0];
  unsigned int yGrid = this->NumberOfControlPoints[1];
  unsigned int xRes = this->Resolution[0];
  unsigned int yRes = this->Resolution[1];

#pragma omp parallel for
  for (unsigned int i=0; i<xRes; i++)
    {
    double u;
    u = i / static_cast<double>(xRes - 1);

    for (unsigned int j=0; j<yRes; j++)
      {

      double basisx, basisy;
      double point[3];
      double v;
      v = j / static_cast<double>(yRes - 1);

      point[0] = 0;
      point[1] = 0;
      point[2] = 0;

      for (unsigned int ci=0; ci<xGrid; ci++)
        {
        basisx = static_cast<double>(this->BinomialCoefficientsX[ci])*
          intpow(u,ci)*intpow((1-u),(xGrid-1-ci));

        for (unsigned int cj=0; cj<yGrid; cj++)
          {
          basisy = static_cast<double>(this->BinomialCoefficientsY[cj])*
            intpow(v,cj)*intpow((1-v),(yGrid-1-cj));

          double *controlPoint = this->ControlPoints[ci]+cj*3;

          point[0] += controlPoint[0] * basisx * basisy;
          point[1] += controlPoint[1] * basisx * basisy;
          point[2] += controlPoint[2] * basisx * basisy;

          }
        }
      DataArray->SetTuple(i*yRes+j,point);

      double tcoord[2] = {u,v};
      TCoords->SetTuple(i*yRes+j, tcoord);
      }
    }
  //END: parallel for

  points->SetData(this->DataArray.GetPointer());

}
